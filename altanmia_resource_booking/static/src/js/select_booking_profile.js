odoo.define('altanmia_resource_booking.select_booking_profile', function (require) {
'use strict';

var publicWidget = require('web.public.widget');

publicWidget.registry.BookingProfileSelect = publicWidget.Widget.extend({
    selector: '.b_booking_choice',
    events: {
        'change select[id="bookingProfile"]': '_onBookingChange',
    },

    /**
     * @constructor
     */
    init: function () {
        this._super.apply(this, arguments);
        // Check if we cannot replace this by a async handler once the related
        // task is merged in master
        this._onBookingChange = _.debounce(this._onBookingChange, 250);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * On appointment type change: adapt appointment intro text and available
     * employees (if option enabled)
     *
     * @override
     * @param {Event} ev
     */
    _onBookingChange: function (ev) {
        var self = this;
        const appointmentTypeID = $(ev.target).val();
        this.$(".b_website_booking_form").attr('action', `/booking/${appointmentTypeID}/profile`);
        this._rpc({
            route: `/booking/${appointmentTypeID}/get_message_intro`,
        }).then(function (message_intro) {
            self.$('.b_calendar_intro').empty().append(message_intro);
        });
    },
});
});
