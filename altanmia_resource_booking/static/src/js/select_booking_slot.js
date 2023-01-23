odoo.define('altanmia_resource_booking.select_booking_slot', function (require) {
'use strict';


var core = require('web.core');
var publicWidget = require('web.public.widget');
var qweb = core.qweb;
var clicks = 0;
var appointments = [];
var numberOfAppointments = 1;
var rpc = require('web.rpc');
var selectedDaysSlots = {};
var slotDate = null;

publicWidget.registry.bookingSlotSelect = publicWidget.Widget.extend({
    selector: '.o_appointment',
    xmlDependencies: [
        '/altanmia_resource_booking/static/src/xml/calendar_booking_slots.xml',
        '/altanmia_resource_booking/static/src/xml/booking_times.xml',
         '/altanmia_resource_booking/static/src/xml/booking_submit.xml',
         '/altanmia_resource_booking/static/src/xml/booking_calendar.xml',
         '/altanmia_resource_booking/static/src/xml/booking_recurrence_form.xml'
         ],
    events: {
        'change select[name="timezone"]': '_onRefresh',
        'change select[id="selectEmployee"]': '_onRefresh',
        'click .o_js_calendar_navigate': '_onCalendarNavigate',
        'click .o_day': '_onClickDaySlot',
        'click .o_time': '_onTimeClick',
        'click .dropdown-item-number': '_onNumberClick',
        'click .dropdown-item-type': '_onTypeClick',
        'change .repeat_until': '_onRepeatUntilChange',
        'change .repeat_unit': '_onRepeatUnitChange',
        'change .available_days': '_onDaysChange',
        'mouseover .input_number': '_onRepeatNumberClick',
        'click .pre_submit': '_onRecuurenceDoneClick',
        'change .month_days_order': '_onRepeatWeekChange',
        'change .input_repeat_every': '_onRepeatIntervalChange',
        'change #multi': '_selectMultiBooking',
        'change #recurring': '_selectRecurringBooking',
        'change #booking_num': '_change_number_booking',
        'click .js_add_booking_num': '_onAddBookingNumber',
        'click .js_sub_booking_num': '_onSubBookingNumber',
    },


    _onAddBookingNumber: async function(ev){
        clicks = 0;
        appointments = [];
        selectedDaysSlots = {};
//        var elt = document.getElementById('booking_num_label');
        var maxBooking = 10;
        numberOfAppointments = parseInt($("#booking_num").val());
        await this._rpc({
                 route: `/booking/max`,
            }).then((result) => {
                maxBooking = result;
            });

        if (numberOfAppointments > (maxBooking -1) ){
            return;
        }

        numberOfAppointments++;
        $("#booking_num").val(numberOfAppointments);
//        elt.innerHTML = numberOfAppointments;

        // CHECK IF ANY DAY IS SELECTED
        if ($('.o_slot_selected')[0]){
            const appointmentTypeID = this.$("input[name='appointment_type_id']").val();
            const appointmentTypeIDs = this.$("input[name='filter_appointment_type_ids']").val();
            var slots = JSON.parse(this.$('.o_slot_selected').find('div')[0].dataset['availableSlots']);
            this._renderSlots(slots, appointmentTypeID, appointmentTypeIDs);
        }
    },

    _onSubBookingNumber: async function(ev){
        clicks = 0;
        appointments = [];
        selectedDaysSlots = {};
//        var elt = document.getElementById('booking_num_label');
        numberOfAppointments = parseInt($("#booking_num").val());
        if (numberOfAppointments < 2){
            return;
        }
        numberOfAppointments--;
        $("#booking_num").val(numberOfAppointments);
//        elt.innerHTML = numberOfAppointments;

        // CHECK IF ANY DAY IS SELECTED
        if ($('.o_slot_selected')[0]){
            const appointmentTypeID = this.$("input[name='appointment_type_id']").val();
            const appointmentTypeIDs = this.$("input[name='filter_appointment_type_ids']").val();
            var slots = JSON.parse(this.$('.o_slot_selected').find('div')[0].dataset['availableSlots']);
            this._renderSlots(slots, appointmentTypeID, appointmentTypeIDs);
        }
    },

    _change_number_booking: function (ev){
        clicks = 0;
        appointments = [];
        selectedDaysSlots = {};

//        var elt = document.getElementById('booking_num_label');
        numberOfAppointments = parseInt($("#booking_num").val());

        if (numberOfAppointments > 10 || numberOfAppointments < 1 || isNaN(numberOfAppointments)){
            numberOfAppointments = 1;
        }
        $("#booking_num").val(numberOfAppointments);
//        elt.innerHTML = numberOfAppointments;

        // CHECK IF ANY DAY IS SELECTED
        if ($('.o_slot_selected')[0]){
            const appointmentTypeID = this.$("input[name='appointment_type_id']").val();
            const appointmentTypeIDs = this.$("input[name='filter_appointment_type_ids']").val();
            var slots = JSON.parse(this.$('.o_slot_selected').find('div')[0].dataset['availableSlots']);
            this._renderSlots(slots, appointmentTypeID, appointmentTypeIDs);
        }
    },

    /**
     * Navigate between the months available in the calendar displayed
     */
    _onCalendarNavigate: function (ev) {
        var parent = this.$('.o_appointment_month:not(.d-none)');
        let monthID = parseInt(parent.attr('id').split('-')[1]);
        monthID += ((this.$(ev.currentTarget).attr('id') === 'nextCal') ? 1 : -1);
        parent.addClass('d-none');
        this.$(`div#month-${monthID}`).removeClass('d-none');
    },

    /**
     * Refresh the slots info when the user modify the timezone or the employee
     */
    _onRefresh: function (ev) {
        if (this.$("#slots_availabilities")[0]) {
            var self = this;
            const appointmentTypeID = this.$("input[name='book_profile_id']").val();
            const employeeID = this.$("#slots_form select[name='employee_id']").val();
            const timezone = this.$("select[name='timezone']").val();
            this._rpc({
                route: `/booking/${appointmentTypeID}/update_available_slots`,
                params: {
                    employee_id: employeeID,
                    timezone: timezone,
                },
            }).then(function (data) {
                if (data) {
                    self.$("#slots_availabilities").replaceWith(data);
                }
            });
        }
    },

    _selectMultiBooking: function(ev){

        var self = this;
        const appointmentTypeID = $("#slots_form input[name='book_profile_id']").val();
        const filterID = $("#slots_form select[name='filter_book_profile_ids']").val();
        const timezone = $("select[name='timezone']").val();
        this._rpc({
            route: `/booking/${appointmentTypeID}/multi`,
            params: {
                    filter_booking_ids: filterID,
                    timezone: timezone,
                },
            }).then(function (data) {
                if (data) {
                    if ($('.appointments_recurrence_form').length){
                        $('.appointments_recurrence_form').replaceWith(data);
                    }else
                    {
                        self.$("#slots_availabilities").replaceWith(data);
                    }

                }
            });
    },

    _selectRecurringBooking: async function(ev){
        if($('#slots_availabilities').length){
            $('#slots_availabilities').remove();
        }
        else if ($('.appointments_recurrence_form').length){
            return;
        }
        let $typeSelection = $('.o_booking_profile_select');

        $(qweb.render('altanmia_resource_booking.repeat_every')).insertAfter($typeSelection);
        const $repeatEvery = $('.repeat_every');
        const availableDays = await this._getAvailableDays();
        $(qweb.render('altanmia_resource_booking.repeat_on', {days: availableDays})).insertAfter($repeatEvery);
        $('.available_days').val($('.available_days option:first').val());

        const availableHours = await this._getAvailableHours($('.available_days').val());
        const $availableDaysDiv = $('.available_days');
        $(qweb.render('altanmia_resource_booking.available_hours', {hours: availableHours})).insertAfter($availableDaysDiv);
        const $repeatOn = $('.repeat_on');
        $(qweb.render('altanmia_resource_booking.repeat_type')).insertAfter($repeatOn);
        const $repeatUntil = $('.repeat_until');
        $(qweb.render('altanmia_resource_booking.input_number')).insertAfter($repeatUntil);
        const $repeatType = $('.repeat_type');
        $(qweb.render('altanmia_resource_booking.done')).insertAfter($repeatType);
    },

    _validateRecurrenceInput: function(ev){
        var validInput = true;
        if (this.$('.input_repeat_every').val()){
            if (parseInt(this.$('.input_repeat_every').val()) > parseInt(this.$('.input_repeat_every').attr('max')) ||
                parseInt(this.$('.input_repeat_every').val()) < parseInt(this.$('.input_repeat_every').attr('min'))){
                    alert(`The entered value for Repeat Every is outside the available range!
                   Choose between ${parseInt(this.$('.input_repeat_every').attr('min'))} and ${parseInt(this.$('.input_repeat_every').attr('max'))}`);
                    validInput = false;
                }
        }
        if (this.$('.input_number').val()){
            if (parseInt(this.$('.input_number').val()) > parseInt(this.$('.input_number').attr('max')) ||
                parseInt(this.$('.input_number').val()) < parseInt(this.$('.input_number').attr('min'))){
                    alert(`The entered value for Repeat Until is outside the available range!
                    Choose between ${parseInt(this.$('.input_number').attr('min'))} and ${parseInt(this.$('.input_number').attr('max'))}`);
                    validInput = false;
                }
        }
        if (!this.$('.input_repeat_every').val() ||
            this.$('.repeat_until').find(":selected").text() === 'Number of Repetition' && !this.$('.input_number').val() ||
            this.$('.repeat_until').find(":selected").text() === 'End Date' && !this.$('.input_date').val()){
            alert("There is some input fields are not specified yet!");
            validInput = false;
        }
        return validInput;
    },

    _onRepeatIntervalChange: function(){
        this.$('.input_number').val('');
    },

    _onRepeatWeekChange: function(){
        this.$('.input_number').val('');
    },

    _onRecuurenceDoneClick: async function(ev){
        if (!this._validateRecurrenceInput()){
            return;
        }
        // TODO: 1 - Get all entered values from view (repeat_unit, repeat_day, repeat_week, repeat_interval, repeat_type, repeat_until)
        const repeatUnit = $('.repeat_unit').find(":selected").text();
        const repeatDay = $('.available_days').find(":selected").text();
        var repeatWeek = -1;
        if ($('.month_days_order').length){
            repeatWeek = $('.month_days_order').find("selected").text();
        }
        const repeatInterval = parseInt($('.input_repeat_every').val())
        const repeatType = $('.repeat_until').find(":selected").text();
        var repeatUntil = null;
        if (repeatType === 'Number of Repetition'){
            repeatUntil = parseInt($('.input_number').val());
        }
        else if (repeatType === 'End Date'){
            var date = new Date($('.input_date').val());
            var day = (date.getDate()) < 10 ? '0' + date.getDate() : date.getDate();
            var month = (date.getMonth() + 1) < 10 ? '0' + (date.getMonth() + 1) : (date.getMonth() + 1);
            var year = date.getFullYear();
            repeatUntil = `${year}-${month}-${day}`
        }
        const repeatHour = $('.available_hours').find(":selected").text();

        // TODO: 2 - Get appointment type info (employee_id, appointment_type_id)
        const employeeID = $("#slots_form select[name='employee_id']").val();
        const appointmentTypeID = $("input[name='book_profile_id']").val();
        const appointmentType = document.getElementsByClassName('o_page_header')[0].innerText;
        const slugifiedName = appointmentType.toLowerCase().replace(/ /g, '-').replace(/[^\w-]+/g, '');

        // TODO: 3 - Get recurrent dates using this._rpc
        // TODO: 4 - Create a list of JSON objects for appointments (Check first the returend date type)
        await this._rpc({
                model: 'tanmia.booking.book.profile',
                method : 'get_recurring_dates',
                args: [[], [repeatUnit,
                            repeatDay,
                            repeatWeek,
                            repeatInterval,
                            repeatUntil,
                            repeatHour,
                            appointmentTypeID,
                            employeeID]
                ],
            }).then((result) => {
                appointments = result;
            });
        // TODO: 5 - Replace Done button with submit button alongside with stringified appointments info (href formatted)
        if(appointments.length > 0){
            $(ev.currentTarget).replaceWith(
                $(qweb.render('altanmia_resource_booking.booking_submit', {
                    booking_profile_id: appointmentTypeID,
                    slugified_name: slugifiedName,
                    booking_dates: encodeURIComponent(JSON.stringify(appointments))
                }))
            );
        }
    },

    _onRepeatNumberClick: async function(ev){
        if (this.$('.repeat_until').find(":selected").text() === 'Number of Repetition' &&
            $('.input_repeat_every').val() &&
            $('.input_repeat_every').val() >= parseInt($('.input_repeat_every').attr('min')) &&
            $('.input_repeat_every').val() <= parseInt($('.input_repeat_every').attr('max'))){
            let dates = null;
            let maxRepeat = null;
            const repeatUnit = $('.repeat_unit').find(":selected").text();
            const repeatDay = $('.available_days').find(":selected").text();
            var repeatWeek = -1;
            if ($('.month_days_order').length){
                repeatWeek = $('.month_days_order').find(":selected").val();
            }
            const repeatInterval = parseInt($('.input_repeat_every').val())
            const repeatType = $('.repeat_until').find(":selected").text();
            const appointmentTypeID = $("input[name='book_profile_id']").val();
            await this._rpc({
                model: 'tanmia.booking.book.profile',
                method : 'get_max_recurrence_repeat',
                args: [[], [repeatUnit,
                            repeatDay,
                            repeatWeek,
                            repeatInterval,
                            appointmentTypeID]
                ],
            }).then((result) => {
                console.log(result);
                dates = result[0];
                maxRepeat = result[1];
            });
            if(dates && maxRepeat){
                $(ev.currentTarget).prop('max',maxRepeat);
                if (maxRepeat === 0){
                    $(ev.currentTarget).prop('min',maxRepeat);
                }
            }
        }
    },

    _getAvailableDays: async function(){
        const appointmentTypeID = $("input[name='book_profile_id']").val();
        const employeeID = $("#slots_form select[name='employee_id']").val();
        const timezone = $("input[name='timezone']").val();
        let availableDays = null;
        await this._rpc({
                model: 'tanmia.booking.book.profile',
                method : 'get_available_days',
                args: [[], [timezone, employeeID, appointmentTypeID]],
        }).then((result) => {
            availableDays = result;
        });

        if(availableDays){
            return availableDays;
        }

        return null;
    },

    _getAvailableHours: async function(day){
        const appointmentTypeID = $("input[name='book_profile_id']").val();
        const employeeID = $("#slots_form select[name='employee_id']").val();
        const timezone = $("input[name='timezone']").val();
        let availableHours = null;
        await this._rpc({
                model: 'tanmia.booking.book.profile',
                method : 'get_available_hours',
                args: [[], [timezone, employeeID, appointmentTypeID, day]],
        }).then((result) => {
            availableHours = result;
        });

        if(availableHours){
            return availableHours;
        }

        return null;
    },

    _onTimeClick: function (ev) {
        if (this.$("#slots_availabilities")[0]) {
            clicks++;
            if (clicks <= numberOfAppointments){
                const timeSelected = this.$(ev.currentTarget).text();
                const appointmentTypeID = $("input[name='book_profile_id']").val();
                const appointmentTypeIDs = $("input[name='filter_book_profile_ids']").val();
                var slots = JSON.parse($('.o_slot_selected').find('div')[0].dataset['availableSlots']);

                $.each(slots , function(index, value) {
                    if (value['hours'] === timeSelected){
                        appointments.push(value);
                        return false;
                    }
                });

                if (slotDate in selectedDaysSlots){
                    slots = selectedDaysSlots[slotDate]
                }

                slots = slots.filter(e1 => !appointments.find(e2 => (e1.hours === e2.hours && e1.datetime === e2.datetime)));
                selectedDaysSlots[slotDate] = slots

                this._renderSlots(slots, appointmentTypeID, appointmentTypeIDs);
            }
            if (clicks === numberOfAppointments){
                this.$('#slotsList').empty();
                const appointmentTypeID = this.$("input[name='book_profile_id']").val();
                const appointmentType = document.getElementsByClassName('o_page_header')[0].innerText;
                const slugifiedName = appointmentType.toLowerCase().replace(/ /g, '-').replace(/[^\w-]+/g, '');

                //Replace the slots list by submit button
                let $slotsList = this.$('#slotsList').empty();
                $(qweb.render('altanmia_resource_booking.booking_submit', {
                    booking_profile_id: appointmentTypeID,
                    slugified_name: slugifiedName,
                    booking_dates: encodeURIComponent(JSON.stringify(appointments))
                })).appendTo($slotsList);
            }
        }
    },

    _onClickDaySlot: function (ev) {
        if (clicks < numberOfAppointments){
            this.$('.o_slot_selected').removeClass('o_slot_selected');
            this.$(ev.currentTarget).addClass('o_slot_selected');

            const appointmentTypeID = this.$("input[name='book_profile_id']").val();
            const appointmentTypeIDs = this.$("input[name='filter_book_profile_ids']").val();
            slotDate = this.$(ev.currentTarget.firstElementChild).attr('id');
            
            var slots = []
            if (typeof this.$(ev.currentTarget).find('div')[0].dataset['availableSlots'] !== 'undefined'){
                slots = JSON.parse(this.$(ev.currentTarget).find('div')[0].dataset['availableSlots']);
            }

            if (slotDate in selectedDaysSlots){
                slots = selectedDaysSlots[slotDate];
            }

            this._renderSlots(slots, appointmentTypeID, appointmentTypeIDs);
        }
    },

    _onNumberClick: function(ev){
        clicks = 0;
        appointments = [];
        selectedDaysSlots = {};
        numberOfAppointments = parseInt(this.$(ev.currentTarget).text());

        // CHECK IF ANY DAY IS SELECTED
        if ($('.o_slot_selected')[0]){
            const appointmentTypeID = this.$("input[name='appointment_type_id']").val();
            const appointmentTypeIDs = this.$("input[name='filter_appointment_type_ids']").val();
            var slots = JSON.parse(this.$('.o_slot_selected').find('div')[0].dataset['availableSlots']);
            this._renderSlots(slots, appointmentTypeID, appointmentTypeIDs);
        }
    },

    _onTypeClick: async function(ev){
        const typeOfAppointment = this.$(ev.currentTarget).text();
        let $typeSelection = this.$('.o_appointment_type_select');
        appointments = []
        var selectedDaysSlots = {};
        var slotDate = null;

        if (typeOfAppointment === 'Regular Appointment'){
            const result = await this._getCalendarInfo();
            const calendar = result[0];
            const formatedDays = result[1];
            const timezone = this.$("input[name='timezone']").val();
            if (calendar){
                if ($('.appointments_recurrence_form').length){
                    $('.appointments_recurrence_form').replaceWith(
                        $(qweb.render('tanmya_appointments.appointments_calendar', {
                            slots: calendar,
                            formated_days: formatedDays,
                            timezone: timezone
                        }))
                    );
                }
                else if($('#slots_availabilities').length){
                    return;
                }
                else {
                    $(qweb.render('tanmya_appointments.appointments_calendar', {
                        slots: calendar,
                        formated_days: formatedDays,
                        timezone: timezone
                    })).insertAfter($typeSelection);
                }
            }
        }
        else if (typeOfAppointment === 'Recurring Appointment'){
            if($('#slots_availabilities').length){
                $('#slots_availabilities').remove();
            }
            else if ($('.appointments_recurrence_form').length){
                return;
            }
            this._renderRecurringForm();
        }
    },

    _onRepeatUntilChange: async function(){
        const $repeatType = this.$('.repeat_until');
        const repeatTypeText = this.$('.repeat_until').find(":selected").text();
        if(repeatTypeText === 'Number of Repetition'){
            if($('.input_date').length){
                $('.input_date').replaceWith($(qweb.render('altanmia_resource_booking.input_number')));
            }
            else{
                $(qweb.render('altanmia_resource_booking.input_number')).insertAfter($repeatType);
            }
        }
        else if(repeatTypeText === 'End Date'){
            if($('.input_number').length){
                $('.input_number').replaceWith($(qweb.render('altanmia_resource_booking.input_date')));
                await this._setMaxScheduleDate();
            }
            else{
                $(qweb.render('altanmia_resource_booking.input_date')).insertAfter($repeatType);
                await this._setMaxScheduleDate();
            }
        }
    },

    _setMaxScheduleDate: async function(){
        const appointmentTypeID = $("input[name='book_profile_id']").val();
        var maxScheduleDays = 0;
        await this._rpc({
        model: 'tanmia.booking.book.profile',
        method : 'get_max_schedule_days',
        args: [[], [appointmentTypeID]],
        }).then((result) => {
            maxScheduleDays = result;
        });
        if(maxScheduleDays){
            $('.input_date').datepicker({
              dateFormat: "yy-mm-dd",
              maxDate: maxScheduleDays,
              minDate: 0,
              pickTime: false,
              singleDatePicker: true,
             });
            $('.input_date').attr("placeholder", "Choose a date");
        }
    },

    _onRepeatUnitChange: function(){
        this.$('.input_number').val('');
        const repeatUnitSelected = this.$('.repeat_unit').find(":selected").text();
        if (repeatUnitSelected == 'Weeks'){
            if ($('.month_days_order').length){
                $('.month_days_order').remove();
            }
        }
        else{
            const $availableDays = this.$('.available_days');
            $(qweb.render('altanmia_resource_booking.month_days_order')).insertBefore($availableDays);
        }
    },

    _onDaysChange: async function(){
        this.$('.input_number').val('');
        const daySelected = this.$('.available_days').find(":selected").text();
        const $prevAvailableHours = this.$('.available_hours').empty();
        const availableHours = await this._getAvailableHours(daySelected);
        for (var i = 0 ; i < availableHours.length ; i++) {
            $prevAvailableHours.append($('<option/>', {
                value: availableHours[i]['hours'],
                text: availableHours[i]['hours'],
            }));
        }
    },

    _renderSlots: function(slots, appointmentTypeID, appointmentTypeIDs){
        let $slotsList = this.$('#slotsList').empty();
        $(qweb.render('altanmia_resource_booking.slots_list', {
            slotDate: moment(slotDate).format("dddd D MMMM"),
            slots: slots,
            book_profile_id: appointmentTypeID,
            filter_book_profile_ids: appointmentTypeIDs,
        })).appendTo($slotsList);
    }
});
});
