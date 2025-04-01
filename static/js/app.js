let tg = window.Telegram.WebApp;
let currentActivity = null;
let timer = null;
let seconds = 0;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    updateDateTime();
    setInterval(updateDateTime, 1000);
    loadDailyStats();
    loadCategories();
    
    // Обработчики событий
    document.getElementById('startTaskBtn').addEventListener('click', startTask);
    document.getElementById('finishTaskBtn').addEventListener('click', finishTask);
    document.getElementById('addTaskManually').addEventListener('click', showAddTaskModal);
});

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
            document.getElementById('currentTask').textContent = taskName;
            document.getElementById('taskControls').classList.remove('hidden');
            document.getElementById('taskInput').value = '';
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
            document.getElementById('currentTask').textContent = '';
            document.getElementById('taskControls').classList.add('hidden');
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
        
        const height = maxDuration > 0 ? (durations[index] / maxDuration) * 100 : 0;
        column.style.height = `${height}%`;
        
        const tooltip = document.createElement('div');
        tooltip.className = 'chart-tooltip';
        tooltip.textContent = `${hour}:00 - ${durations[index]} мин`;
        
        column.appendChild(tooltip);
        chartContainer.appendChild(column);
    });
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

// Отображение ошибки
function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = message;
    errorDiv.classList.remove('hidden');
    setTimeout(() => {
        errorDiv.classList.add('hidden');
    }, 3000);
}

// Показать модальное окно добавления задачи
function showAddTaskModal() {
    document.getElementById('addTaskModal').classList.remove('hidden');
}

// Закрыть модальное окно
function closeModal(modalId) {
    document.getElementById(modalId).classList.add('hidden');
}

// Инициализация Telegram Web App
tg.expand(); 