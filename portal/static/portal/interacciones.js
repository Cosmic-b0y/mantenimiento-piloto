(() => {
  const description = document.getElementById("id_descripcion");
  const count = document.getElementById("description-count");
  if (description && count) {
    const updateCount = () => { count.textContent = description.value.length + " / 2500"; };
    description.addEventListener("input", updateCount);
    updateCount();
  }

  const file = document.getElementById("id_evidencia");
  const preview = document.getElementById("photo-preview");
  let previewUrl;
  if (file && preview) {
    file.addEventListener("change", () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      preview.hidden = true;
      preview.removeAttribute("src");
      const selected = file.files[0];
      if (selected && ["image/jpeg", "image/png"].includes(selected.type) && selected.size <= 5 * 1024 * 1024) {
        previewUrl = URL.createObjectURL(selected);
        preview.src = previewUrl;
        preview.hidden = false;
      }
    });
  }
})();
