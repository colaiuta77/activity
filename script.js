// 사용자 활동 데이터를 안전한 DOM 요소로 변환하고 필터 상호작용을 처리합니다.
(function () {
  'use strict';

  const root = document.getElementById('activity-page');
  if (!root) return;

  const elements = {
    refresh: root.querySelector('#activity-refresh'),
    user: root.querySelector('#activity-user-filter'),
    period: root.querySelector('#activity-period-filter'),
    sort: root.querySelector('#activity-sort-filter'),
    state: root.querySelector('#activity-state'),
    users: root.querySelector('#activity-users'),
    summaryUsers: root.querySelector('#activity-summary-users'),
    summaryTotal: root.querySelector('#activity-summary-total'),
    summaryProgress: root.querySelector('#activity-summary-progress'),
    summaryCompleted: root.querySelector('#activity-summary-completed'),
  };
  const pageState = {
    dbType: document.getElementById('btn-lib-adult')?.classList.contains('active') ? 'adult' : 'general',
    items: [],
    summary: {},
    preferences: {},
  };

  function number(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function formatDate(value) {
    if (!value) return '열람 시각 없음';
    const normalized = String(value).replace('T', ' ');
    return normalized.slice(0, 16);
  }

  function activityTimestamp(item) {
    const value = Date.parse(String(item.last_read_at || '').replace(' ', 'T'));
    return Number.isFinite(value) ? value : 0;
  }

  function setText(element, value) {
    if (element) element.textContent = String(value);
  }

  function showState(message, iconClass) {
    elements.users.replaceChildren();
    elements.state.replaceChildren();
    const icon = document.createElement('i');
    icon.className = iconClass;
    icon.setAttribute('aria-hidden', 'true');
    elements.state.append(icon, document.createTextNode(` ${message}`));
    elements.state.hidden = false;
  }

  function updateUserOptions(items) {
    const selected = elements.user.value;
    const usernames = [...new Set(items.map((item) => String(item.username || '')))]
      .filter(Boolean)
      .sort((a, b) => a.localeCompare(b, 'ko'));
    elements.user.replaceChildren();
    const allOption = document.createElement('option');
    allOption.value = 'all';
    allOption.textContent = '전체 사용자';
    elements.user.appendChild(allOption);
    usernames.forEach((username) => {
      const option = document.createElement('option');
      option.value = username;
      option.textContent = username;
      elements.user.appendChild(option);
    });
    elements.user.value = usernames.includes(selected) ? selected : 'all';
  }

  function filteredItems() {
    const selectedUser = elements.user.value;
    const periodDays = number(elements.period.value);
    const cutoff = periodDays ? Date.now() - periodDays * 24 * 60 * 60 * 1000 : 0;
    const items = pageState.items.filter((item) => {
      if (selectedUser !== 'all' && item.username !== selectedUser) return false;
      if (cutoff && activityTimestamp(item) < cutoff) return false;
      return true;
    });

    const sort = elements.sort.value;
    items.sort((a, b) => {
      if (sort === 'progress') {
        return number(b.progress_percent) - number(a.progress_percent) || activityTimestamp(b) - activityTimestamp(a);
      }
      if (sort === 'username') {
        return String(a.username).localeCompare(String(b.username), 'ko') || activityTimestamp(b) - activityTimestamp(a);
      }
      return activityTimestamp(b) - activityTimestamp(a);
    });
    return items;
  }

  function createBookCard(item) {
    const card = document.createElement('article');
    card.className = 'activity-book-card';
    card.tabIndex = 0;
    card.setAttribute('role', 'button');
    card.setAttribute('aria-label', `${item.title || '제목 없음'} 상세 보기`);

    const cover = document.createElement('img');
    cover.className = 'activity-cover';
    cover.src = item.cover || '/static/images/default_cover.jpg';
    cover.alt = `${item.title || '도서'} 표지`;
    cover.loading = 'lazy';
    cover.addEventListener('error', () => {
      cover.src = '/static/images/default_cover.jpg';
    }, { once: true });

    const main = document.createElement('div');
    main.className = 'activity-book-main';
    const topLine = document.createElement('div');
    topLine.className = 'activity-book-topline';
    const title = document.createElement('h3');
    title.className = 'activity-book-title';
    title.textContent = item.title || '제목 없음';
    title.title = item.title || '제목 없음';
    const badge = document.createElement('span');
    badge.className = `activity-status-badge${item.is_completed ? ' is-complete' : ''}`;
    badge.textContent = item.is_completed ? '완독' : '진행 중';
    topLine.append(title, badge);

    const progressTrack = document.createElement('div');
    progressTrack.className = 'activity-progress-track';
    progressTrack.setAttribute('role', 'progressbar');
    progressTrack.setAttribute('aria-valuemin', '0');
    progressTrack.setAttribute('aria-valuemax', '100');
    progressTrack.setAttribute('aria-valuenow', String(number(item.progress_percent)));
    const progressFill = document.createElement('div');
    progressFill.className = 'activity-progress-fill';
    progressFill.style.width = `${Math.max(0, Math.min(100, number(item.progress_percent)))}%`;
    progressTrack.appendChild(progressFill);

    const progressRow = document.createElement('div');
    progressRow.className = 'activity-progress-row';
    const pages = document.createElement('span');
    pages.textContent = number(item.total_pages)
      ? `${number(item.pages_read).toLocaleString()}/${number(item.total_pages).toLocaleString()}페이지`
      : `${number(item.pages_read).toLocaleString()}페이지`;
    const percent = document.createElement('strong');
    percent.textContent = `${number(item.progress_percent)}%`;
    progressRow.append(pages, percent);

    const time = document.createElement('div');
    time.className = 'activity-book-time';
    const timeIcon = document.createElement('i');
    timeIcon.className = 'fa-regular fa-clock';
    timeIcon.setAttribute('aria-hidden', 'true');
    const timeValue = document.createElement('time');
    timeValue.dateTime = String(item.last_read_at || '');
    timeValue.textContent = formatDate(item.last_read_at);
    time.append(timeIcon, timeValue);

    main.append(topLine, progressTrack, progressRow, time);
    card.append(cover, main);

    const openDetail = (event) => {
      if (typeof window.openBookDetail === 'function') {
        window.openBookDetail(
          event,
          item.series_name || item.title || '',
          item.library_id || null,
          item.book_id || null,
          item.title || ''
        );
      }
    };
    card.addEventListener('click', openDetail);
    card.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openDetail(event);
      }
    });
    return card;
  }

  function render() {
    const items = filteredItems();
    const usernames = new Set(items.map((item) => item.username));
    const completed = items.filter((item) => item.is_completed).length;
    const allFilters = elements.user.value === 'all' && elements.period.value === 'all';
    setText(elements.summaryUsers, allFilters ? number(pageState.summary.users).toLocaleString() : usernames.size.toLocaleString());
    setText(elements.summaryTotal, allFilters ? number(pageState.summary.total_activities).toLocaleString() : items.length.toLocaleString());
    setText(elements.summaryProgress, (items.length - completed).toLocaleString());
    setText(elements.summaryCompleted, completed.toLocaleString());

    if (!items.length) {
      showState('선택한 조건에 맞는 사용자 활동이 없습니다.', 'fa-solid fa-book-open');
      return;
    }

    const groups = new Map();
    items.forEach((item) => {
      if (!groups.has(item.username)) groups.set(item.username, []);
      groups.get(item.username).push(item);
    });
    elements.users.replaceChildren();
    elements.state.hidden = true;

    groups.forEach((userItems, username) => {
      const section = document.createElement('section');
      section.className = 'activity-user-section';
      const header = document.createElement('header');
      header.className = 'activity-user-header';
      const heading = document.createElement('h2');
      heading.className = 'activity-user-title';
      const avatar = document.createElement('span');
      avatar.className = 'activity-user-avatar';
      avatar.textContent = String(username || '?').slice(0, 1).toUpperCase();
      const name = document.createElement('span');
      name.textContent = username;
      heading.append(avatar, name);
      header.appendChild(heading);

      if (pageState.preferences.show_user_summary !== false) {
        const count = document.createElement('span');
        count.className = 'activity-user-count';
        const total = number(userItems[0]?.user_total_activities);
        count.textContent = `최근 ${userItems.length}건 / 전체 ${total}건`;
        header.appendChild(count);
      }

      const grid = document.createElement('div');
      grid.className = 'activity-book-grid';
      userItems.forEach((item) => grid.appendChild(createBookCard(item)));
      section.append(header, grid);
      elements.users.appendChild(section);
    });
  }

  async function loadActivity() {
    elements.refresh.disabled = true;
    showState('활동 데이터를 불러오는 중입니다.', 'fa-solid fa-circle-notch fa-spin');
    try {
      const response = await fetch(`/api/media/dashboard/widgets/activity/data?type=${encodeURIComponent(pageState.dbType)}&limit=100`);
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || '활동 데이터를 불러오지 못했습니다.');
      pageState.items = Array.isArray(data.items) ? data.items.filter((item) => !item.item_type && item.username) : [];
      pageState.summary = data.summary || {};
      pageState.preferences = data.preferences || {};
      elements.sort.value = pageState.preferences.default_sort || 'recent';
      updateUserOptions(pageState.items);
      render();
    } catch (error) {
      showState(error.message || '사용자 활동을 불러오지 못했습니다.', 'fa-solid fa-triangle-exclamation');
    } finally {
      elements.refresh.disabled = false;
    }
  }

  elements.refresh.addEventListener('click', loadActivity);
  elements.user.addEventListener('change', render);
  elements.period.addEventListener('change', render);
  elements.sort.addEventListener('change', render);
  loadActivity();
})();
