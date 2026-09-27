const loader = document.getElementById("loader");
const site = document.getElementById("site");
const revealSite = () => {
  loader.classList.add("hide");
  site.classList.add("ready");
};
window.addEventListener("load", () => setTimeout(revealSite, 1250));
setTimeout(revealSite, 3500);

const menuToggle = document.getElementById("menuToggle");
const nav = document.getElementById("nav");
menuToggle.addEventListener("click", () => {
  const open = nav.classList.toggle("open");
  menuToggle.setAttribute("aria-expanded", String(open));
});
nav.querySelectorAll("a").forEach(link => link.addEventListener("click", () => {
  nav.classList.remove("open");
  menuToggle.setAttribute("aria-expanded", "false");
}));

// Avoid fake social destinations: placeholder links stay on the page until real URLs are added.
document.querySelectorAll('.socials a[href="#"]').forEach(link => {
  link.addEventListener("click", event => event.preventDefault());
});
