import * as bootstrap from "bootstrap";
import htmx from "htmx.org";
import Alpine from "alpinejs";

// Exposed globally so templates can use data attributes and inline Alpine expressions.
window.bootstrap = bootstrap;
window.htmx = htmx;
window.Alpine = Alpine;

// Bootstrap's "lg" breakpoint, where the sidebar switches between the in-flow
// layout and the off-canvas drawer (see assets/scss/app.scss).
const desktopMediaQuery = window.matchMedia("(min-width: 992px)");
// Read before the first paint by the inline script in templates/base.html.
const SIDEBAR_COLLAPSED_STORAGE_KEY = "sololedger.sidebarCollapsed";
const SIDEBAR_COLLAPSED_CLASS = "app-sidebar-collapsed";

Alpine.data("appLayout", () => ({
  isDesktop: desktopMediaQuery.matches,
  // Desktop: the sidebar is collapsed out of the flow and remembered across pages.
  isCollapsed: document.documentElement.classList.contains(SIDEBAR_COLLAPSED_CLASS),
  // Mobile: the sidebar is an off-canvas drawer, closed on every page load.
  isDrawerOpen: false,

  init() {
    desktopMediaQuery.addEventListener("change", (event) => {
      this.isDesktop = event.matches;
      if (this.isDesktop) {
        this.isDrawerOpen = false;
      }
    });
  },

  get isSidebarOpen() {
    return this.isDesktop ? !this.isCollapsed : this.isDrawerOpen;
  },

  toggleSidebar() {
    if (this.isDesktop) {
      this.toggleCollapsed();
    } else if (this.isDrawerOpen) {
      this.closeSidebar();
    } else {
      this.openDrawer();
    }
  },

  toggleCollapsed() {
    this.isCollapsed = !this.isCollapsed;
    document.documentElement.classList.toggle(SIDEBAR_COLLAPSED_CLASS, this.isCollapsed);
    try {
      localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, String(this.isCollapsed));
    } catch (error) {
      // Storage can be unavailable (e.g. private browsing): the preference is not kept.
    }
  },

  openDrawer() {
    this.isDrawerOpen = true;
    this.$nextTick(() => this.$refs.sidebarClose?.focus());
  },

  closeSidebar() {
    if (!this.isDrawerOpen) {
      return;
    }
    this.isDrawerOpen = false;
    this.$refs.sidebarToggle?.focus();
  },
}));

Alpine.start();
