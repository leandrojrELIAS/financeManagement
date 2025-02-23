// Adicionar funcionalidade para confirmar exclusões
document.addEventListener('DOMContentLoaded', function () {
    const deleteForms = document.querySelectorAll('form[action^="/delete"]');

    deleteForms.forEach(form => {
        form.addEventListener('submit', function (e) {
            const confirmation = confirm("Você tem certeza que deseja excluir este item?");
            if (!confirmation) {
                e.preventDefault(); // Cancela o envio do formulário
            }
        });
    });
});

// Exemplo de customização interativa para troca de cores na navbar
const colorPicker = document.getElementById('cor_navbar');
if (colorPicker) {
    colorPicker.addEventListener('change', function () {
        document.querySelector('.sidebar').style.backgroundColor = colorPicker.value;
    });
}
