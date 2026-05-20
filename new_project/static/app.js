function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let n = bytes;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(1)} ${units[i]}`;
}

function showToast(message, type = 'success') {
  const el = document.getElementById('toast');
  el.textContent = message;
  el.className = `toast ${type}`;
  setTimeout(() => el.classList.add('hidden'), 4000);
}

document.addEventListener('DOMContentLoaded', () => {
  const storageEl = document.getElementById('storage-size');
  if (storageEl) {
    storageEl.textContent = formatBytes(parseInt(storageEl.textContent, 10) || 0);
  }
});

document.getElementById('add-app-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  const data = Object.fromEntries(new FormData(form));
  data.retention_days = parseInt(data.retention_days, 10);
  if (!data.db_connection) data.db_connection = null;
  if (!data.schedule_cron) data.schedule_cron = null;
  if (!data.description) data.description = null;

  try {
    const res = await fetch('/api/applications', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Ошибка создания');
    }
    showToast('Приложение добавлено');
    location.reload();
  } catch (err) {
    showToast(err.message, 'error');
  }
});

async function runBackup(appId) {
  try {
    const res = await fetch(`/api/applications/${appId}/backups`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Ошибка бэкапа');
    showToast(`Бэкап #${data.id}: ${data.status}`);
    setTimeout(() => location.reload(), 800);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function showBackups(appId, name) {
  const modal = document.getElementById('backups-modal');
  document.getElementById('modal-title').textContent = `Бэкапы: ${name}`;
  const content = document.getElementById('modal-content');
  content.innerHTML = '<p>Загрузка...</p>';
  modal.showModal();

  const res = await fetch(`/api/applications/${appId}/backups`);
  const backups = await res.json();
  if (!backups.length) {
    content.innerHTML = '<p class="empty">Нет бэкапов</p>';
    return;
  }
  content.innerHTML = `
    <table class="data-table">
      <thead><tr><th>ID</th><th>Статус</th><th>Размер</th><th>Дата</th><th></th></tr></thead>
      <tbody>
        ${backups.map(b => `
          <tr>
            <td>${b.id}</td>
            <td><span class="badge ${b.status}">${b.status}</span></td>
            <td>${formatBytes(b.size_bytes)}</td>
            <td>${new Date(b.started_at).toLocaleString('ru-RU')}</td>
            <td>
              ${b.status === 'success' ? `<button class="btn small" onclick="restoreBackup(${b.id})">Восстановить</button>` : ''}
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>`;
}

async function restoreBackup(backupId) {
  if (!confirm('Восстановить из этого бэкапа? Текущие файлы будут перезаписаны.')) return;
  try {
    const res = await fetch(`/api/backups/${backupId}/restore`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Ошибка восстановления');
    showToast(`Восстановлено: ${data.restored_to}`);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function deleteApp(appId) {
  if (!confirm('Удалить приложение и все его бэкапы?')) return;
  const res = await fetch(`/api/applications/${appId}`, { method: 'DELETE' });
  if (res.ok) {
    showToast('Приложение удалено');
    location.reload();
  } else {
    showToast('Ошибка удаления', 'error');
  }
}

async function deleteBackup(backupId) {
  if (!confirm('Удалить этот бэкап?')) return;
  const res = await fetch(`/api/backups/${backupId}`, { method: 'DELETE' });
  if (res.ok) {
    showToast('Бэкап удалён');
    location.reload();
  } else {
    showToast('Ошибка удаления', 'error');
  }
}
