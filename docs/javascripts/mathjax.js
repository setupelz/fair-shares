window.MathJax = {
  tex: {
    inlineMath: [
      ["\\(", "\\)"],
      ["$", "$"],
    ],
    displayMath: [
      ["\\[", "\\]"],
      ["$$", "$$"],
    ],
    processEscapes: true,
    processEnvironments: true,
    packages: ["base", "ams", "noerrors", "noundefined"],
  },
  options: {
    skipHtmlTags: ["script", "noscript", "style", "textarea", "pre"],
    ignoreHtmlClass: "tex2jax_ignore",
    processHtmlClass: "tex2jax_process",
    renderActions: {
      addMenu: [0, "", ""],
    },
  },
  startup: {
    pageReady: () => {
      // Delay initial typesetting to let collapsible-api.js manipulate
      // the DOM first (it runs on DOMContentLoaded). Math inside closed
      // <details> is rendered on toggle via collapsible-api.js.
      return new Promise((resolve) => {
        setTimeout(() => {
          MathJax.startup.defaultPageReady().then(resolve);
        }, 200);
      });
    },
  },
};
