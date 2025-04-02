let tg = window.Telegram.WebApp;
let currentUser = null;
let currentActivity = null;
let timer = null;
let startTime = null;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Инициализируем Telegram WebApp
        tg.expand();
        tg.enableClosingConfirmation();
        
        // Получаем данные пользователя
        currentUser = tg.initDataUnsafe.user;
        console.log('Initial user data:', currentUser);
        
        if (!currentUser) {
            throw new Error('No user data available');
        }
        
        // Загружаем данные пользователя
        await loadUserData();
        console.log('Updated user data:', currentUser);
        
        // Загружаем категории
        await loadCategories();
        
        // Загружаем статистику
        await loadStats();
        
        // Настраиваем обработчики событий
        setupEventListeners();
        
        // Обновляем интерфейс
        updateUserInterface();
    } catch (error) {
        console.error('Error initializing app:', error);
        showError('Ошибка инициализации приложения');
    }
});

// Загрузка данных пользователя
async function loadUserData() {
    try {
        console.log('Loading user data for:', currentUser);
        const response = await fetch(`/api/user?user=${encodeURIComponent(JSON.stringify(currentUser))}`);
        if (!response.ok) {
            throw new Error('Failed to load user data');
        }
        const userData = await response.json();
        console.log('Received user data:', userData);
        currentUser = { ...currentUser, ...userData };
        updateUserInterface();
    } catch (error) {
        console.error('Error loading user data:', error);
        showError('Ошибка загрузки данных пользователя');
    }
}

// Загрузка категорий
async function loadCategories() {
    if (!currentUser || !currentUser.telegram_id) return;
    try {
        const response = await fetch(`/api/stats/categories?user=${encodeURIComponent(JSON.stringify({ id: currentUser.telegram_id }))}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const categories = await response.json();
        updateCategoriesList(categories);
    } catch (error) {
        console.error('Error loading categories:', error);
        showError('Не удалось загрузить категории.');
    }
}

// Загрузка статистики
async function loadStats() {
    try {
        const response = await fetch(`/api/stats/daily?user=${encodeURIComponent(JSON.stringify({ id: currentUser.telegram_id }))}`);
        if (!response.ok) {
            throw new Error('Failed to load stats');
        }
        const stats = await response.json();
        updateStats(stats);
    } catch (error) {
        console.error('Error loading stats:', error);
        showError('Ошибка загрузки статистики');
    }
}

// Настройка обработчиков событий
function setupEventListeners() {
    // Навигация
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const screen = item.getAttribute('data-screen');
            showScreen(screen);
        });
    });
    
    // Таймер
    const startButton = document.getElementById('startTimer');
    const finishButton = document.getElementById('finishTimer');
    const categorySelect = document.getElementById('categorySelect');
    
    if (startButton) {
        startButton.addEventListener('click', startTask);
    }
    
    if (finishButton) {
        finishButton.addEventListener('click', finishTask);
    }
    
    if (categorySelect) {
        categorySelect.addEventListener('change', () => {
            const selectedCategory = categorySelect.value;
            if (selectedCategory) {
                startButton.disabled = false;
            } else {
                startButton.disabled = true;
            }
        });
    }
    
    // Настройки
    const themeToggle = document.getElementById('themeToggle');
    const notificationsToggle = document.getElementById('notificationsToggle');
    const dailyGoalInput = document.getElementById('dailyGoal');
    const breakReminderInput = document.getElementById('breakReminder');
    
    if (themeToggle) {
        themeToggle.addEventListener('change', () => {
            updateTheme(themeToggle.checked ? 'dark' : 'light');
        });
    }
    
    if (notificationsToggle) {
        notificationsToggle.addEventListener('change', () => {
            updateNotifications(notificationsToggle.checked);
        });
    }
    
    if (dailyGoalInput) {
        dailyGoalInput.addEventListener('change', () => {
            updateDailyGoal(parseInt(dailyGoalInput.value));
        });
    }
    
    if (breakReminderInput) {
        breakReminderInput.addEventListener('change', () => {
            updateBreakReminder(parseInt(breakReminderInput.value));
        });
    }
}

// Обновление интерфейса
function updateUserInterface() {
    if (!currentUser) return;
    
    // Обновляем имя пользователя
    const usernameElement = document.getElementById('username');
    if (usernameElement) {
        usernameElement.textContent = currentUser.first_name || currentUser.username || 'Пользователь';
    }
    
    // Обновляем статистику
    const levelElement = document.getElementById('userLevel');
    const xpElement = document.getElementById('userXP');
    if (levelElement) levelElement.textContent = currentUser.level;
    if (xpElement) xpElement.textContent = currentUser.xp;
    
    // Обновляем настройки
    const themeToggle = document.getElementById('themeToggle');
    const notificationsToggle = document.getElementById('notificationsToggle');
    const dailyGoalInput = document.getElementById('dailyGoal');
    const breakReminderInput = document.getElementById('breakReminder');
    
    if (themeToggle) themeToggle.checked = currentUser.theme === 'dark';
    if (notificationsToggle) notificationsToggle.checked = currentUser.notifications;
    if (dailyGoalInput) dailyGoalInput.value = currentUser.daily_goal;
    if (breakReminderInput) breakReminderInput.value = currentUser.break_reminder;
    
    // Применяем тему
    updateTheme(currentUser.theme);
}

// Обновление списка категорий
function updateCategoriesList(categories) {
    const categorySelect = document.getElementById('categorySelect');
    if (!categorySelect) return;
    
    categorySelect.innerHTML = '<option value="">Выберите категорию</option>';
    categories.forEach(category => {
        const option = document.createElement('option');
        option.value = category.id;
        option.textContent = category.name;
        categorySelect.appendChild(option);
    });
}

// Обновление статистики
function updateStats(stats) {
    const totalTimeElement = document.getElementById('totalTime');
    const totalTasksElement = document.getElementById('totalTasks');
    const productivityElement = document.getElementById('productivity');
    
    if (totalTimeElement) {
        totalTimeElement.textContent = `${Math.round(stats.total_time / 60)} мин`;
    }
    
    if (totalTasksElement) {
        totalTasksElement.textContent = stats.total_tasks;
    }
    
    if (productivityElement) {
        productivityElement.textContent = `${stats.productivity}/5`;
    }
}

// Показ экрана
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    document.getElementById(screenId).classList.add('active');
    
    // Обновляем активный пункт меню
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('data-screen') === screenId) {
            item.classList.add('active');
        }
    });
}

// Запуск задачи
async function startTask() {
    try {
        const categoryId = document.getElementById('categorySelect').value;
        const taskName = document.getElementById('taskName').value || 'Новая задача';
        
        const response = await fetch('/api/activity/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user: currentUser,
                category_id: categoryId,
                name: taskName
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to start activity');
        }
        
        const data = await response.json();
        currentActivity = data;
        startTime = new Date();
        
        // Обновляем UI
        document.getElementById('startTimer').disabled = true;
        document.getElementById('finishTimer').disabled = false;
        document.getElementById('categorySelect').disabled = true;
        document.getElementById('taskName').disabled = true;
        
        // Запускаем таймер
        startTimer();
        
        // Показываем уведомление
        showNotification('Задача начата!');
    } catch (error) {
        console.error('Error starting task:', error);
        showError('Ошибка запуска задачи');
    }
}

// Завершение задачи
async function finishTask() {
    try {
        if (!currentActivity) {
            throw new Error('No active task');
        }
        
        const notes = document.getElementById('taskNotes').value;
        const productivity = document.getElementById('productivityRating').value;
        
        const response = await fetch('/api/activity/finish', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user: currentUser,
                activity_id: currentActivity.id,
                notes: notes,
                productivity: parseInt(productivity)
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to finish activity');
        }
        
        const data = await response.json();
        
        // Останавливаем таймер
        stopTimer();
        
        // Сбрасываем UI
        document.getElementById('startTimer').disabled = false;
        document.getElementById('finishTimer').disabled = true;
        document.getElementById('categorySelect').disabled = false;
        document.getElementById('taskName').disabled = false;
        document.getElementById('taskNotes').value = '';
        document.getElementById('productivityRating').value = '3';
        
        // Обновляем статистику
        await loadStats();
        
        // Показываем уведомление
        showNotification(`Задача завершена! Получено ${data.xp_earned} XP`);
        
        currentActivity = null;
        startTime = null;
    } catch (error) {
        console.error('Error finishing task:', error);
        showError('Ошибка завершения задачи');
    }
}

// Таймер
function startTimer() {
    if (timer) return;
    
    timer = setInterval(() => {
        const now = new Date();
        const diff = now - startTime;
        const minutes = Math.floor(diff / 60000);
        const seconds = Math.floor((diff % 60000) / 1000);
        
        document.getElementById('timer').textContent = 
            `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }, 1000);
}

function stopTimer() {
    if (timer) {
        clearInterval(timer);
        timer = null;
    }
}

// Обновление настроек
async function updateTheme(theme) {
    if (!currentUser || !currentUser.telegram_id) return;
    document.body.className = theme;
    try {
        const response = await fetch('/api/settings/theme', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user: { id: currentUser.telegram_id },
                theme: theme
            })
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
    } catch (error) {
        console.error('Error updating theme:', error);
        showError('Не удалось обновить тему.');
    }
}

async function updateNotifications(enabled) {
    if (!currentUser || !currentUser.telegram_id) return;
    try {
        const response = await fetch('/api/settings/notifications', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user: { id: currentUser.telegram_id },
                notifications: enabled
            })
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
    } catch (error) {
        console.error('Error updating notifications:', error);
    }
}

async function updateDailyGoal(minutes) {
    if (!currentUser || !currentUser.telegram_id) return;
    try {
        const response = await fetch('/api/settings/daily_goal', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user: { id: currentUser.telegram_id },
                daily_goal: minutes
            })
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
    } catch (error) {
        console.error('Error updating daily goal:', error);
    }
}

async function updateBreakReminder(minutes) {
    if (!currentUser || !currentUser.telegram_id) return;
    try {
        const response = await fetch('/api/settings/break_reminder', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user: { id: currentUser.telegram_id },
                break_reminder: minutes
            })
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
    } catch (error) {
        console.error('Error updating break reminder:', error);
    }
}

// Уведомления
function showNotification(message) {
    const notification = document.createElement('div');
    notification.className = 'notification';
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('show');
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 3000);
    }, 100);
}

function showError(message) {
    const error = document.createElement('div');
    error.className = 'error';
    error.textContent = message;
    
    document.body.appendChild(error);
    
    setTimeout(() => {
        error.classList.add('show');
        setTimeout(() => {
            error.classList.remove('show');
            setTimeout(() => {
                error.remove();
            }, 300);
        }, 3000);
    }, 100);
} 