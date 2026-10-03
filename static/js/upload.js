// Upload zones (apps/ui/widgets.py): drag and drop, and the chosen file's name and size.
document.addEventListener("DOMContentLoaded", () => {
  for (const zone of document.querySelectorAll("[data-upload]")) {
    const input = zone.querySelector("input[type=file]");
    const label = zone.querySelector("[data-upload-file]");
    const show = () => {
      const file = input.files[0];
      label.hidden = !file;
      if (file) {
        const size = file.size < 1024 * 1024
          ? `${Math.max(1, Math.round(file.size / 1024))} KB`
          : `${(file.size / 1024 / 1024).toFixed(1)} MB`;
        label.textContent = `Tanlangan fayl: ${file.name}, ${size}`;
      }
    };
    input.addEventListener("change", show);
    zone.addEventListener("dragover", (event) => {
      event.preventDefault();
      zone.classList.add("is-dragging");
    });
    zone.addEventListener("dragleave", () => zone.classList.remove("is-dragging"));
    zone.addEventListener("drop", (event) => {
      event.preventDefault();
      zone.classList.remove("is-dragging");
      if (event.dataTransfer.files.length) {
        input.files = event.dataTransfer.files;
        show();
      }
    });
  }
});

// The submit button during the cooldown (docs/UI.md §5): counts the seconds down, then
// lets the student send. Without JavaScript the page shows the wait and a reload frees it.
document.addEventListener("DOMContentLoaded", () => {
  for (const button of document.querySelectorAll("[data-cooldown]")) {
    const label = button.textContent.replace(/\s*\(\d+ s\)$/, "");
    let left = Number(button.dataset.cooldown);
    const tick = () => {
      left -= 1;
      if (left <= 0) {
        button.disabled = false;
        button.textContent = label;
        return;
      }
      button.textContent = `${label} (${left} s)`;
      setTimeout(tick, 1000);
    };
    setTimeout(tick, 1000);
  }
});
