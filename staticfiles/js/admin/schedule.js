// src/data_processing/static/js/admin/schedule.js
document.addEventListener('DOMContentLoaded', function() {
    // Get form elements
    const frequencyField = document.getElementById('id_frequency');
    const weekDaysContainer = document.querySelector('.field-week_days');
    const dayOfMonthContainer = document.querySelector('.field-day_of_month');
    
    if (!frequencyField) return; // Exit if not on schedule form
    
    // Initial setup
    toggleFields();
    
    // Add event listener
    frequencyField.addEventListener('change', toggleFields);
    
    function toggleFields() {
        const frequency = frequencyField.value;
        
        // Hide all optional fields first
        if (weekDaysContainer) weekDaysContainer.style.display = 'none';
        if (dayOfMonthContainer) dayOfMonthContainer.style.display = 'none';
        
        // Show relevant fields
        if (frequency === 'weeks' && weekDaysContainer) {
            weekDaysContainer.style.display = 'block';
        } 
        else if (frequency === 'months' && dayOfMonthContainer) {
            dayOfMonthContainer.style.display = 'block';
        }
    }
});