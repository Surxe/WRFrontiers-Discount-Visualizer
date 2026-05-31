export function initAllWeeksSidebar() {
  const drawerToggle = document.getElementById('sidebar-toggle');
  const container = document.getElementById('layout-container');

  if (!drawerToggle || !container) return;

  function setSidebarHidden(isHidden) {
    container.classList.toggle('sidebar-hidden', isHidden);
    drawerToggle.setAttribute('aria-expanded', String(!isHidden));
    localStorage.setItem('sidebar-hidden', String(isHidden));
  }

  setSidebarHidden(localStorage.getItem('sidebar-hidden') === 'true');

  drawerToggle.addEventListener('click', () => {
    setSidebarHidden(!container.classList.contains('sidebar-hidden'));
  });
}
