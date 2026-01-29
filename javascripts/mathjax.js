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
    // Process math in hidden elements (like closed <details>)
    renderActions: {
      addMenu: [0, "", ""],
    },
  },
  startup: {
    pageReady: () => {
      // Delay initial typesetting slightly to let collapsible-api.js
      // manipulate the DOM first (it runs on DOMContentLoaded)
      return new Promise((resolve) => {
        setTimeout(() => {
          MathJax.startup.defaultPageReady().then(resolve);
        }, 100);
      });
    },
  },
};
