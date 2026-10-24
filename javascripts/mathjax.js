window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true,
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex",
  },
};

document$.subscribe(() => {
  if (typeof MathJax !== "undefined" && MathJax.startup) {
    MathJax.startup.promise.then(() => {
      const content = document.querySelector(".md-content");
      if (content) {
        MathJax.typesetClear([content]);
        MathJax.typesetPromise([content]);
      }
    });
  }
});
