export function initAllWeeksSidebar() {
  const desktopToggle = document.getElementById('sidebar-toggle');
  const mobileToggle = document.getElementById('mobile-sidebar-toggle');
  const container = document.getElementById('layout-container');
  const sidebarContent = document.getElementById('sidebar-content');
  const scrollbarTrack = document.getElementById('custom-scrollbar-track');
  const scrollbarThumb = document.getElementById('custom-scrollbar-thumb');

  if (!container) return;

  const SIDEBAR_HIDDEN_KEY = 'sidebar-hidden';
  const storedSidebarHidden = localStorage.getItem(SIDEBAR_HIDDEN_KEY);
  const isMobileDefault = window.matchMedia('(max-width: 768px)').matches;

  function updateMobileTopBarIcons(isHidden) {
    if (!mobileToggle) return;
    const openIcon = mobileToggle.querySelector('.topbar-icon-open');
    const closeIcon = mobileToggle.querySelector('.topbar-icon-close');
    if (openIcon) openIcon.style.display = isHidden ? 'block' : 'none';
    if (closeIcon) closeIcon.style.display = isHidden ? 'none' : 'block';
  }

  function setSidebarHidden(isHidden) {
    container.classList.toggle('sidebar-hidden', isHidden);
    if (desktopToggle) desktopToggle.setAttribute('aria-expanded', String(!isHidden));
    if (mobileToggle) mobileToggle.setAttribute('aria-expanded', String(!isHidden));
    updateMobileTopBarIcons(isHidden);
    localStorage.setItem(SIDEBAR_HIDDEN_KEY, String(isHidden));
  }

  const defaultHidden = storedSidebarHidden === null ? isMobileDefault : storedSidebarHidden === 'true';
  setSidebarHidden(defaultHidden);

  function onToggleClick() {
    const willHide = !container.classList.contains('sidebar-hidden');
    setSidebarHidden(willHide);
  }

  if (desktopToggle) desktopToggle.addEventListener('click', onToggleClick);
  if (mobileToggle) mobileToggle.addEventListener('click', onToggleClick);
  // Custom scrollbar functionality
  if (sidebarContent && scrollbarTrack && scrollbarThumb) {
    let isDragging = false;
    let startY = 0;
    let startScrollTop = 0;

    function updateScrollbar() {
      const scrollHeight = sidebarContent.scrollHeight;
      const clientHeight = sidebarContent.clientHeight;
      const scrollTop = sidebarContent.scrollTop;
      const trackHeight = window.innerHeight; // Track is fixed to viewport
      
      if (scrollHeight <= clientHeight) {
        scrollbarThumb.style.display = 'none';
        return;
      }
      
      scrollbarThumb.style.display = 'block';
      
      const thumbHeight = (clientHeight / scrollHeight) * trackHeight;
      const thumbPosition = (scrollTop / (scrollHeight - clientHeight)) * (trackHeight - thumbHeight);
      
      scrollbarThumb.style.height = `${thumbHeight}px`;
      scrollbarThumb.style.transform = `translateY(${thumbPosition}px)`;
    }

    // Update scrollbar on scroll
    sidebarContent.addEventListener('scroll', updateScrollbar);
    
    // Update scrollbar on resize
    window.addEventListener('resize', updateScrollbar);
    
    // Initial update
    updateScrollbar();

    // Drag functionality
    scrollbarThumb.addEventListener('mousedown', (e) => {
      isDragging = true;
      startY = e.clientY;
      startScrollTop = sidebarContent.scrollTop;
      scrollbarThumb.style.transition = 'none';
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      
      const deltaY = e.clientY - startY;
      const scrollHeight = sidebarContent.scrollHeight;
      const clientHeight = sidebarContent.clientHeight;
      const trackHeight = window.innerHeight;
      const thumbHeight = (clientHeight / scrollHeight) * trackHeight;
      
      const scrollDelta = (deltaY / (trackHeight - thumbHeight)) * (scrollHeight - clientHeight);
      sidebarContent.scrollTop = startScrollTop + scrollDelta;
    });

    document.addEventListener('mouseup', () => {
      if (isDragging) {
        isDragging = false;
        scrollbarThumb.style.transition = 'background-color 0.2s ease, transform 0.1s ease';
      }
    });

    // Click on track to scroll
    scrollbarTrack.addEventListener('click', (e) => {
      if (e.target === scrollbarThumb) return;
      
      const trackRect = scrollbarTrack.getBoundingClientRect();
      const clickY = e.clientY - trackRect.top;
      const scrollHeight = sidebarContent.scrollHeight;
      const clientHeight = sidebarContent.clientHeight;
      const trackHeight = window.innerHeight;
      const thumbHeight = (clientHeight / scrollHeight) * trackHeight;
      
      let targetScrollTop;
      if (clickY < parseFloat(scrollbarThumb.style.transform.replace('translateY(', '').replace('px)', '')) || 0) {
        // Click above thumb
        targetScrollTop = (clickY / trackHeight) * scrollHeight - (clientHeight / 2);
      } else {
        // Click below thumb
        targetScrollTop = (clickY / trackHeight) * scrollHeight - (clientHeight / 2);
      }
      
      sidebarContent.scrollTo({
        top: targetScrollTop,
        behavior: 'smooth'
      });
    });

    // Mouse wheel support with smooth scrolling
    sidebarContent.addEventListener('wheel', (e) => {
      e.preventDefault();
      const delta = e.deltaY;
      const scrollAmount = delta * 2.0; // Adjust scroll speed
      sidebarContent.scrollBy({
        top: scrollAmount,
        behavior: 'smooth'
      });
    }, { passive: false });
  }
}
