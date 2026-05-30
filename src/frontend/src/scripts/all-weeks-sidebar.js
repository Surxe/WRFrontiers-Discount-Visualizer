export function initAllWeeksSidebar() {
  const drawerToggle = document.getElementById('sidebar-toggle');
  const container = document.getElementById('layout-container');
  const sidebar = document.getElementById('sidebar');
  const popup = document.getElementById('next-week-popup');
  const popupClose = document.getElementById('next-week-popup-close');

  if (!drawerToggle || !container) return;

  function syncSidebarWidth() {
    if (!sidebar) return;
    const content = sidebar.querySelector('.sidebar-content');
    const width = content
      ? content.getBoundingClientRect().width
      : sidebar.getBoundingClientRect().width;
    document.documentElement.style.setProperty('--sidebar-width', `${width}px`);
  }

  function setDrawerOpen(isOpen) {
    container.classList.toggle('sidebar-open', isOpen);
    drawerToggle.setAttribute('aria-expanded', String(isOpen));
    localStorage.setItem('sidebar-open', String(isOpen));
    if (isOpen) {
      requestAnimationFrame(syncSidebarWidth);
    }
  }

  syncSidebarWidth();
  window.addEventListener('resize', syncSidebarWidth);

  setDrawerOpen(localStorage.getItem('sidebar-open') === 'true');

  drawerToggle.addEventListener('click', () => {
    setDrawerOpen(!container.classList.contains('sidebar-open'));
  });

  if (popup && popupClose) {
    const nextSlug = popup.getAttribute('data-next-slug');
    const dismissKey = `next-week-popup-dismissed-${nextSlug}`;
    if (localStorage.getItem(dismissKey) === 'true') {
      popup.hidden = true;
    }
    popupClose.addEventListener('click', () => {
      popup.hidden = true;
      localStorage.setItem(dismissKey, 'true');
    });
  }
}
