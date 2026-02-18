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
      return new Promise((resolve) => {
        function doTypeset() {
          // Open all collapsibles so MathJax has valid layout dimensions
          var allDetails = document.querySelectorAll(
            "details.doc-method-collapsible, details.mathematical-foundation",
          );
          allDetails.forEach(function (d) {
            d.setAttribute("open", "");
          });

          MathJax.startup.defaultPageReady().then(function () {
            // Close method collapsibles after render (leave mathematical-foundation open)
            document
              .querySelectorAll("details.doc-method-collapsible")
              .forEach(function (d) {
                d.removeAttribute("open");
              });
            resolve();
          });
        }
        // Gate on DOMContentLoaded so collapsible-api.js has finished
        if (document.readyState === "loading") {
          document.addEventListener("DOMContentLoaded", doTypeset, {
            once: true,
          });
        } else {
          doTypeset();
        }
      });
    },
  },
};
