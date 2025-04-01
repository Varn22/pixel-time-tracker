let tg = window.Telegram.WebApp;
let currentActivity = null;
let timer = null;
let seconds = 0;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    if (!tg.initDataUnsafe || !tg.initDataUnsafe.user) {
        showError('Ошибка инициализации Telegram WebApp');
        return;
    }
    
    initializeApp();
    setupEventListeners();
    loadUserData();
    loadCategories();
    setupScreens();
});

// Инициализация приложения
function initializeApp() {
    tg.expand();
    updateDateTime();
    setInterval(updateDateTime, 1000);
    loadDailyStats();
}

// Настройка экранов
function setupScreens() {
    const screens = document.querySelectorAll('.screen');
    screens.forEach(screen => {
        screen.style.display = 'none';
    });
    document.getElementById('main-screen').style.display = 'block';
}

// Настройка обработчиков событий
function setupEventListeners() {
    // Обработчики кнопок навигации
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const screenId = item.dataset.screen;
            switchScreen(screenId);
            
            // Обновляем активное состояние
            document.querySelectorAll('.nav-item').forEach(navItem => {
                navItem.classList.remove('active');
            });
            item.classList.add('active');
        });
    });

    // Обработчики действий с задачами
    const startTaskBtn = document.getElementById('startTaskBtn');
    const finishTaskBtn = document.getElementById('finishTaskBtn');
    const addTaskManuallyBtn = document.getElementById('addTaskManually');
    
    if (startTaskBtn) {
        startTaskBtn.addEventListener('click', startTask);
    }
    
    if (finishTaskBtn) {
        finishTaskBtn.addEventListener('click', finishTask);
    }
    
    if (addTaskManuallyBtn) {
        addTaskManuallyBtn.addEventListener('click', showAddTaskModal);
    }

    // Обработчики настроек
    const themeSelect = document.getElementById('themeSelect');
    const notificationsToggle = document.getElementById('notificationsToggle');
    
    if (themeSelect) {
        themeSelect.addEventListener('change', updateTheme);
    }
    
    if (notificationsToggle) {
        notificationsToggle.addEventListener('change', updateNotifications);
    }

    // Обработчик ввода задачи
    const taskInput = document.getElementById('taskInput');
    if (taskInput) {
        taskInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !currentActivity) {
                startTask();
            }
        });
    }
}

// Загрузка данных пользователя
async function loadUserData() {
    try {
        const response = await fetch('/api/user', {
            headers: {
                'X-User-Id': tg.initDataUnsafe.user.id.toString()
            }
        });
        
        if (response.ok) {
            const userData = await response.json();
            updateUserInterface(userData);
        } else {
            showError('Ошибка загрузки данных пользователя');
        }
    } catch (error) {
        console.error('Ошибка при загрузке данных пользователя:', error);
        showError('Ошибка загрузки данных пользователя');
    }
}

// Обновление интерфейса данными пользователя
function updateUserInterface(userData) {
    // Обновляем имя пользователя (обрезаем длинные имена)
    const username = tg.initDataUnsafe.user.username || 'Пользователь';
    const displayName = username.length > 15 ? username.substring(0, 12) + '...' : username;
    
    const usernameElement = document.getElementById('username');
    if (usernameElement) {
        usernameElement.textContent = displayName;
        usernameElement.title = username; // Показываем полное имя при наведении
    }

    // Обновляем профиль
    const profileUsername = document.getElementById('profileUsername');
    if (profileUsername) {
        profileUsername.textContent = username;
    }

    // Обновляем аватар
    const userAvatar = document.getElementById('userAvatar');
    if (userAvatar) {
        if (tg.initDataUnsafe.user.photo_url) {
            userAvatar.src = tg.initDataUnsafe.user.photo_url;
        } else {
            userAvatar.src = 'https://via.placeholder.com/100?text=' + username.charAt(0).toUpperCase();
        }
    }

    // Обновляем уровень и опыт
    if (userData.level) {
        const userLevel = document.getElementById('userLevel');
        if (userLevel) {
            userLevel.textContent = userData.level;
        }
        updateXPProgress(userData.xp);
    }

    // Обновляем настройки
    if (userData.theme) {
        const themeSelect = document.getElementById('themeSelect');
        if (themeSelect) {
            themeSelect.value = userData.theme;
            document.body.setAttribute('data-theme', userData.theme);
        }
    }
    
    if (userData.notifications !== undefined) {
        const notificationsToggle = document.getElementById('notificationsToggle');
        if (notificationsToggle) {
            notificationsToggle.checked = userData.notifications;
        }
    }
}

// Обновление даты и времени
function updateDateTime() {
    const now = new Date();
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    const currentDate = document.getElementById('currentDate');
    if (currentDate) {
        currentDate.textContent = now.toLocaleDateString('ru-RU', options);
    }
    
    if (currentActivity) {
        seconds++;
        updateTimerDisplay();
    }
}

// Отображение таймера
function updateTimerDisplay() {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    const timerElement = document.getElementById('timer');
    if (timerElement) {
        timerElement.textContent = 
            `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
}

// Начало задачи
async function startTask() {
    const taskInput = document.getElementById('taskInput');
    const categorySelect = document.getElementById('categorySelect');
    
    if (!taskInput || !categorySelect) return;
    
    const taskName = taskInput.value.trim();
    const category = categorySelect.value;
    
    if (!taskName) {
        showError('Введите название задачи');
        return;
    }
    
    try {
        const response = await fetch('/api/activity', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-User-Id': tg.initDataUnsafe.user.id.toString()
            },
            body: JSON.stringify({
                name: taskName,
                category: category
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentActivity = data;
            seconds = 0;
            const startTaskBtn = document.getElementById('startTaskBtn');
            const finishTaskBtn = document.getElementById('finishTaskBtn');
            
            if (startTaskBtn) startTaskBtn.classList.add('hidden');
            if (finishTaskBtn) finishTaskBtn.classList.remove('hidden');
            
            taskInput.disabled = true;
            categorySelect.disabled = true;
            
            showError('Задача начата', 'success');
        } else {
            showError(data.error || 'Ошибка при запуске задачи');
        }
    } catch (error) {
        showError('Ошибка при запуске задачи');
    }
}

// Завершение задачи
async function finishTask() {
    if (!currentActivity) return;
    
    try {
        const response = await fetch('/api/activity/stop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-User-Id': tg.initDataUnsafe.user.id.toString()
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentActivity = null;
            seconds = 0;
            const timerElement = document.getElementById('timer');
            const startTaskBtn = document.getElementById('startTaskBtn');
            const finishTaskBtn = document.getElementById('finishTaskBtn');
            const taskInput = document.getElementById('taskInput');
            const categorySelect = document.getElementById('categorySelect');
            
            if (timerElement) timerElement.textContent = '00:00:00';
            if (startTaskBtn) startTaskBtn.classList.remove('hidden');
            if (finishTaskBtn) finishTaskBtn.classList.add('hidden');
            if (taskInput) {
                taskInput.value = '';
                taskInput.disabled = false;
            }
            if (categorySelect) categorySelect.disabled = false;
            
            loadDailyStats();
            showError('Задача завершена', 'success');
        } else {
            showError(data.error || 'Ошибка при завершении задачи');
        }
    } catch (error) {
        showError('Ошибка при завершении задачи');
    }
}

// Загрузка статистики за день
async function loadDailyStats() {
    try {
        const response = await fetch('/api/stats/daily', {
            headers: {
                'X-User-Id': tg.initDataUnsafe.user.id.toString()
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            updateActivityChart(data.hours, data.durations);
        } else {
            showError('Ошибка загрузки статистики');
        }
    } catch (error) {
        console.error('Ошибка при загрузке статистики:', error);
        showError('Ошибка загрузки статистики');
    }
}

// Обновление графика активности
function updateActivityChart(hours, durations) {
    const chartContainer = document.getElementById('activityChart');
    if (!chartContainer) return;
    
    chartContainer.innerHTML = '';
    
    const maxDuration = Math.max(...durations, 60); // Минимальная высота для пустых столбцов
    
    hours.forEach((hour, index) => {
        const column = document.createElement('div');
        column.className = 'chart-column';
        
        const bar = document.createElement('div');
        bar.className = 'chart-bar';
        const height = (durations[index] / maxDuration) * 100;
        bar.style.height = `${height}%`;
        
        // Добавляем тултип с информацией
        const minutes = Math.round(durations[index]);
        bar.title = `${hour}:00 - ${minutes} мин.`;
        
        column.setAttribute('data-time', hour);
        column.appendChild(bar);
        chartContainer.appendChild(column);
    });
}

// Переключение экранов
function switchScreen(screenId) {
    const screens = document.querySelectorAll('.screen');
    screens.forEach(screen => {
        screen.style.display = 'none';
    });
    
    const targetScreen = document.getElementById(`${screenId}-screen`);
    if (targetScreen) {
        targetScreen.style.display = 'block';
    }
}

// Обновление темы
function updateTheme(event) {
    const theme = event.target.value;
    document.body.setAttribute('data-theme', theme);
    
    fetch('/api/settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-User-Id': tg.initDataUnsafe.user.id.toString()
        },
        body: JSON.stringify({ theme })
    }).catch(error => {
        console.error('Ошибка при обновлении темы:', error);
        showError('Ошибка при обновлении темы');
    });
}

// Обновление настроек уведомлений
function updateNotifications(event) {
    const notifications = event.target.checked;
    
    fetch('/api/settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-User-Id': tg.initDataUnsafe.user.id.toString()
        },
        body: JSON.stringify({ notifications })
    }).catch(error => {
        console.error('Ошибка при обновлении настроек:', error);
        showError('Ошибка при обновлении настроек');
    });
}

// Отображение ошибки
function showError(message, type = 'error') {
    const errorDiv = document.getElementById('error');
    if (!errorDiv) return;
    
    errorDiv.textContent = message;
    errorDiv.className = `error-message ${type}`;
    errorDiv.classList.remove('hidden');
    
    setTimeout(() => {
        errorDiv.classList.add('hidden');
    }, 3000);
}

// Обновление прогресса опыта
function updateXPProgress(xp) {
    const xpForNextLevel = (Math.floor(xp / 100) + 1) * 100;
    const currentLevelXP = Math.floor(xp / 100) * 100;
    const progress = ((xp - currentLevelXP) / (xpForNextLevel - currentLevelXP)) * 100;
    
    const progressBar = document.getElementById('xpProgress');
    if (progressBar) {
        progressBar.style.width = `${progress}%`;
    }
}

// Загрузка категорий
async function loadCategories() {
    try {
        const response = await fetch('/api/stats/categories', {
            headers: {
                'X-User-Id': tg.initDataUnsafe.user.id.toString()
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            updateCategorySelect(data);
        } else {
            showError('Ошибка загрузки категорий');
        }
    } catch (error) {
        console.error('Ошибка при загрузке категорий:', error);
        showError('Ошибка загрузки категорий');
    }
}

// Обновление выпадающего списка категорий
function updateCategorySelect(categories) {
    const select = document.getElementById('categorySelect');
    if (!select) return;
    
    select.innerHTML = '';
    
    const defaultOption = document.createElement('option');
    defaultOption.value = 'other';
    defaultOption.textContent = 'Другое';
    select.appendChild(defaultOption);
    
    Object.keys(categories).forEach(category => {
        if (category !== 'other') {
            const option = document.createElement('option');
            option.value = category;
            option.textContent = category;
            select.appendChild(option);
        }
    });
}

// Показать модальное окно добавления задачи
function showAddTaskModal() {
    const modal = document.getElementById('addTaskModal');
    if (modal) {
        modal.classList.remove('hidden');
    }
}

// Закрыть модальное окно
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('hidden');
    }
} 