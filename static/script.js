// Butonu seçiyoruz
const buton = document.getElementById('buton');

// Tıklama olayı ekliyoruz
buton.addEventListener('click', function() {
    alert('Harika! JavaScript dosyası da sorunsuz çalışıyor. 🚀');
    
    // Arka plan rengini rastgele değiştirelim
    document.body.style.backgroundColor = rastgeleRenk();
});

function rastgeleRenk() {
    const harfler = '0123456789ABCDEF';
    let renk = '#';
    for (let i = 0; i < 6; i++) {
        renk += harfler[Math.floor(Math.random() * 16)];
    }
    return renk;
}