// static/js/batchtable.js
$(document).ready(function() {
    $('#batchTable').DataTable({
        dom: 'Bfrtip',
        buttons: [
            'copy', 'csv', 'excel', 'pdf', 'print'
        ],
        scrollX: true,
        autoWidth: false,
        responsive: true,
        language: {
            search: "_INPUT_",
            searchPlaceholder: "Search...",
            paginate: {
                first: "First",
                previous: "Previous",
                next: "Next",
                last: "Last"
            }
        },
        pagingType: "full_numbers", // Use full_numbers for pagination style
        drawCallback: function(settings) {
            // Add custom classes to pagination buttons
            $(this).find('.paginate_button.previous').html('<i class="fas fa-chevron-left"></i>');
            $(this).find('.paginate_button.next').html('<i class="fas fa-chevron-right"></i>');
            $(this).find('.paginate_button.first').html('<i class="fas fa-angle-double-left"></i>');
            $(this).find('.paginate_button.last').html('<i class="fas fa-angle-double-right"></i>');
        }
    });
});