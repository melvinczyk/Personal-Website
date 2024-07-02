const menuButton = document.getElementById('menu-button');
  const sideMenu = document.getElementById('side-menu');
  const overlay = document.getElementById('overlay');

  menuButton.addEventListener('click', () => {
    sideMenu.classList.toggle('-translate-x-full');
    overlay.classList.toggle('hidden');
  });

  overlay.addEventListener('click', () => {
    sideMenu.classList.add('-translate-x-full');
    overlay.classList.add('hidden');
  });