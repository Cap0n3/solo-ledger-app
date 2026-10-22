import * as bootstrap from "bootstrap";
import htmx from "htmx.org";
import Alpine from "alpinejs";

// Exposed globally so templates can use data attributes and inline Alpine expressions.
window.bootstrap = bootstrap;
window.htmx = htmx;
window.Alpine = Alpine;

Alpine.start();
