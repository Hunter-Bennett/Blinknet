const hamburgerBtn = document.getElementById('hamburger-btn');
const hamburgerMenu = document.getElementById('hamburger-menu');

// Toggle menu
hamburgerBtn.addEventListener('click', (e) => {
    e.stopPropagation(); // Prevent the window click from immediately closing it
    hamburgerMenu.style.display = hamburgerMenu.style.display === 'block' ? 'none' : 'block';
});

// Close menu when clicking outside
window.addEventListener('click', (e) => {
    if (!hamburgerMenu.contains(e.target) && e.target !== hamburgerBtn) {
        hamburgerMenu.style.display = 'none';
    }
});
