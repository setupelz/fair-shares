// Make API documentation sections collapsible
(function () {
  function makeParameterRowsCollapsible() {
    // Find all parameter tables
    const tables = document.querySelectorAll(".doc table");

    tables.forEach(function (table) {
      const tbody = table.querySelector("tbody");
      if (!tbody) return;

      const rows = tbody.querySelectorAll("tr.doc-section-item");

      rows.forEach(function (row) {
        if (row.hasAttribute("data-param-collapsible")) {
          return;
        }

        const cells = row.querySelectorAll("td");
        if (cells.length < 4) return; // Need Name, Type, Description, Default

        const nameCell = cells[0];
        const typeCell = cells[1];
        const descCell = cells[2];
        const defaultCell = cells[3];

        // Get parameter name
        const paramName = nameCell.textContent.trim();

        // Create a new row structure with collapsible details
        const newRow = document.createElement("tr");
        newRow.className = "doc-param-collapsible-row";

        // Create summary cell that spans all columns
        const summaryCell = document.createElement("td");
        summaryCell.colSpan = 4;

        const details = document.createElement("details");
        details.className = "doc-param-collapsible";

        const summary = document.createElement("summary");
        summary.className = "doc-param-summary";

        // Summary shows: name (type) - default
        const nameSpan = document.createElement("span");
        nameSpan.className = "param-name";
        nameSpan.innerHTML = nameCell.innerHTML;

        const typeSpan = document.createElement("span");
        typeSpan.className = "param-type";
        typeSpan.innerHTML = " : " + typeCell.textContent.trim();

        summary.appendChild(nameSpan);
        summary.appendChild(typeSpan);

        // Details show description and default in a clean layout
        const detailsContent = document.createElement("div");
        detailsContent.className = "doc-param-details";

        const descDiv = document.createElement("div");
        descDiv.className = "param-description";
        descDiv.innerHTML = descCell.innerHTML;

        const defaultDiv = document.createElement("div");
        defaultDiv.className = "param-default";
        defaultDiv.innerHTML =
          "<strong>Default:</strong> " + defaultCell.innerHTML;

        detailsContent.appendChild(descDiv);
        detailsContent.appendChild(defaultDiv);

        details.appendChild(summary);
        details.appendChild(detailsContent);
        summaryCell.appendChild(details);
        newRow.appendChild(summaryCell);

        // Replace old row with new collapsible row
        row.parentNode.insertBefore(newRow, row);
        row.remove();

        // Mark as processed
        newRow.setAttribute("data-param-collapsible", "true");
      });
    });
  }

  function makeMethodsCollapsible() {
    // Find all doc objects (methods/properties/functions)
    const docObjects = document.querySelectorAll(".doc.doc-object");

    docObjects.forEach(function (docObj) {
      // Skip if already processed
      if (docObj.hasAttribute("data-collapsible")) {
        return;
      }

      // Find heading - could be H2 inside (manager page) or H3 as previous sibling (budgets/pathways page)
      let heading = docObj.querySelector("h2");
      let headingIsInside = true;

      if (!heading) {
        // Check for H3/H4 as previous sibling
        const prevSibling = docObj.previousElementSibling;
        if (
          prevSibling &&
          (prevSibling.tagName === "H3" || prevSibling.tagName === "H4")
        ) {
          heading = prevSibling;
          headingIsInside = false;
        }
      }

      if (!heading) {
        return;
      }

      // Skip the main class/module heading and "See Also" sections
      if (
        heading.textContent.includes("See Also") ||
        heading.id === "allocationmanager"
      ) {
        return;
      }

      // Get the heading text (method/property name)
      const headingText = heading.textContent.replace("¶", "").trim();

      // Create details/summary wrapper
      const details = document.createElement("details");
      details.className = "doc-method-collapsible";
      // Start collapsed
      details.removeAttribute("open");

      const summary = document.createElement("summary");
      summary.className = "doc-method-summary";
      summary.textContent = headingText;

      // Build the details element
      details.appendChild(summary);

      // Move the doc-object content into details
      const contentWrapper = document.createElement("div");
      contentWrapper.className = "doc-method-content";
      contentWrapper.appendChild(docObj.cloneNode(true));
      details.appendChild(contentWrapper);

      // Replace the doc-object with the details element
      docObj.parentNode.insertBefore(details, docObj);
      docObj.remove();

      // If heading was outside, remove it too
      if (!headingIsInside) {
        heading.remove();
      }

      // Mark as processed
      details.setAttribute("data-collapsible", "true");
    });

    // After making methods collapsible, make parameter rows collapsible
    makeParameterRowsCollapsible();
  }

  // Re-typeset MathJax after DOM manipulation
  function retypesetMath() {
    if (typeof MathJax !== "undefined" && MathJax.typesetPromise) {
      MathJax.typesetPromise().catch(function (err) {
        console.warn("MathJax typeset failed:", err);
      });
    }
  }

  // Set up MathJax to run after DOM manipulation completes
  function setupMathJaxHook() {
    // If MathJax is already loaded and ready, typeset now
    if (typeof MathJax !== "undefined" && MathJax.typesetPromise) {
      retypesetMath();
    } else {
      // MathJax not loaded yet - set up a hook to run when it's ready
      // MathJax 3 fires 'ready' promise after startup
      var checkInterval = setInterval(function () {
        if (typeof MathJax !== "undefined" && MathJax.typesetPromise) {
          clearInterval(checkInterval);
          retypesetMath();
        }
      }, 100);
      // Stop checking after 10 seconds to prevent infinite loop
      setTimeout(function () {
        clearInterval(checkInterval);
      }, 10000);
    }
  }

  // Also re-typeset when details elements are opened (for lazy rendering)
  function setupDetailsToggleHandler() {
    document.addEventListener(
      "toggle",
      function (event) {
        if (event.target.tagName === "DETAILS" && event.target.open) {
          // Small delay to let content render
          setTimeout(retypesetMath, 50);
        }
      },
      true,
    );
  }

  // Main initialization function
  function init() {
    makeMethodsCollapsible();
    setupMathJaxHook();
  }

  // Run immediately if DOM is already ready, otherwise wait for DOMContentLoaded
  if (
    document.readyState === "complete" ||
    document.readyState === "interactive"
  ) {
    init();
    setupDetailsToggleHandler();
  } else {
    document.addEventListener("DOMContentLoaded", function () {
      init();
      setupDetailsToggleHandler();
    });
  }

  // Handle MkDocs Material instant navigation (pages loaded via AJAX)
  // The event is dispatched after new content is loaded
  if (typeof document$ !== "undefined") {
    document$.subscribe(function () {
      init();
    });
  } else {
    // Fallback: listen for the custom event that Material dispatches
    document.addEventListener("DOMContentSwitch", function () {
      init();
    });
  }
})();
