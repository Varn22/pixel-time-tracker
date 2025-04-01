let tg = window.Telegram.WebApp;
let currentActivity = null;
let timer = null;
let seconds = 0;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    setupEventListeners();
    loadUserData();
});

// Инициализация приложения
function initializeApp() {
    tg.expand();
    updateDateTime();
    setInterval(updateDateTime, 1000);
    loadDailyStats();
    setupScreens();
}

// Настройка обработчиков событий
function setupEventListeners() {
    // Обработчики кнопок навигации
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => switchScreen(item.dataset.screen));
    });

    // Обработчики действий с задачами
    document.getElementById('startTaskBtn').addEventListener('click', startTask);
    document.getElementById('finishTaskBtn').addEventListener('click', finishTask);
    document.getElementById('addTaskManually').addEventListener('click', showAddTaskModal);

    // Обработчики настроек
    document.getElementById('themeSelect').addEventListener('change', updateTheme);
    document.getElementById('notificationsToggle').addEventListener('change', updateNotifications);
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
        }
    } catch (error) {
        console.error('Ошибка при загрузке данных пользователя:', error);
    }
}

// Обновление интерфейса данными пользователя
function updateUserInterface(userData) {
    // Обновляем имя пользователя
    const usernameElement = document.getElementById('username');
    if (usernameElement) {
        usernameElement.textContent = tg.initDataUnsafe.user.username || 'Пользователь';
    }

    // Обновляем профиль
    const profileUsername = document.getElementById('profileUsername');
    if (profileUsername) {
        profileUsername.textContent = tg.initDataUnsafe.user.username || 'Пользователь';
    }

    // Обновляем аватар
    const userAvatar = document.getElementById('userAvatar');
    if (userAvatar && tg.initDataUnsafe.user.photo_url) {
        userAvatar.src = tg.initDataUnsafe.user.photo_url;
    }

    // Обновляем уровень и опыт
    if (userData.level) {
        document.getElementById('userLevel').textContent = userData.level;
        updateXPProgress(userData.xp);
    }

    // Обновляем настройки
    if (userData.theme) {
        document.getElementById('themeSelect').value = userData.theme;
        document.body.setAttribute('data-theme', userData.theme);
    }
    
    if (userData.notifications !== undefined) {
        document.getElementById('notificationsToggle').checked = userData.notifications;
    }
}

// Обновление даты и времени
function updateDateTime() {
    const now = new Date();
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    document.getElementById('currentDate').textContent = now.toLocaleDateString('ru-RU', options);
    
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
    
    document.getElementById('timer').textContent = 
        `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// Начало задачи
async function startTask() {
    const taskName = document.getElementById('taskInput').value;
    const category = document.getElementById('categorySelect').value;
    
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
            document.getElementById('startTaskBtn').classList.add('hidden');
            document.getElementById('finishTaskBtn').classList.remove('hidden');
            document.getElementById('taskInput').disabled = true;
            document.getElementById('categorySelect').disabled = true;
        } else {
            showError(data.error);
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
            document.getElementById('timer').textContent = '00:00:00';
            document.getElementById('startTaskBtn').classList.remove('hidden');
            document.getElementById('finishTaskBtn').classList.add('hidden');
            document.getElementById('taskInput').value = '';
            document.getElementById('taskInput').disabled = false;
            document.getElementById('categorySelect').disabled = false;
            loadDailyStats();
        } else {
            showError(data.error);
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
        }
    } catch (error) {
        console.error('Ошибка при загрузке статистики:', error);
    }
}

// Обновление графика активности
function updateActivityChart(hours, durations) {
    const chartContainer = document.getElementById('activityChart');
    chartContainer.innerHTML = '';
    
    const maxDuration = Math.max(...durations);
    
    hours.forEach((hour, index) => {
        const column = document.createElement('div');
        column.className = 'chart-column';
        
        const bar = document.createElement('div');
        bar.className = 'chart-bar';
        const height = maxDuration > 0 ? (durations[index] / maxDuration) * 100 : 0;
        bar.style.height = `${height}%`;
        
        column.setAttribute('data-time', hour);
        column.appendChild(bar);
        chartContainer.appendChild(column);
    });
}

// Переключение экранов
function switchScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    document.getElementById(`${screenId}-screen`).classList.add('active');
    
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-screen="${screenId}"]`).classList.add('active');
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
    });
}

// Отображение ошибки
function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = message;
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
        }
    } catch (error) {
        console.error('Ошибка при загрузке категорий:', error);
    }
}

// Обновление выпадающего списка категорий
function updateCategorySelect(categories) {
    const select = document.getElementById('categorySelect');
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
    document.getElementById('addTaskModal').classList.remove('hidden');
}

// Закрыть модальное окно
function closeModal(modalId) {
    document.getElementById(modalId).classList.add('hidden');
} 