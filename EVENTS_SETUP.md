# Events Management System - Setup Guide

## Overview
This is a comprehensive events management system for StoryConnect with the following features:

### User Features:
- **Upcoming Events Carousel**: Browse upcoming events with a beautiful carousel (center card larger, moves one by one)
- **Event Registration**: Sign up for events with a simple form
- **Google Maps Navigation**: Get directions to events with multiple travel modes (driving, walking, bicycling, transit)
- **My Events Section**: View registered events with a calendar
- **Event Submissions**: Submit event proposals for admin approval
- **Submission Management**: View and manage your event submissions with status tracking

### Admin Features:
- **Review Submissions**: View all user-submitted event proposals
- **Approve/Reject**: Review and approve or reject submissions with notes
- **Create Events**: Manually create events or from approved submissions
- **Submission Dashboard**: Track pending, approved, and rejected submissions

## Setup Instructions

### 1. Database Setup

Run the SQL commands in `database_schema.sql` to create the necessary tables:

```sql
-- Run this in your MySQL database
source database_schema.sql;
```

Or manually execute the SQL commands to create:
- `events` table
- `event_registrations` table
- `event_submissions` table

### 2. Google Maps API Key

1. Get your Google Maps API key from [Google Cloud Console](https://console.cloud.google.com/)
2. Enable these APIs:
   - Maps JavaScript API
   - Places API
   - Directions API
   - Geocoding API

3. Add your API key to `config.py`:
   ```python
   GOOGLE_MAPS_API_KEY = 'YOUR_API_KEY_HERE'
   ```

   Or set as environment variable:
   ```bash
   export GOOGLE_MAPS_API_KEY='YOUR_API_KEY_HERE'
   ```

### 3. Admin Setup

To make a user an admin, update their `user_type` in the database:

```sql
UPDATE users SET user_type = 'admin' WHERE email = 'admin@example.com';
```

### 4. File Structure

The events system includes:

```
routes/
  events.py              # Events routes and logic

templates/events/
  events_home.html       # Main events page with carousel, maps, my events
  signup_form.html       # Event signup form
  submit_event.html      # Event submission form (3 sections)
  my_submissions.html    # User's submission management
  admin_submissions.html # Admin view of all submissions
  admin_review.html      # Admin review and approval page
  admin_create_event.html # Admin event creation form

static/
  css/events.css         # Events styling
  uploads/events/        # Event images directory
```

### 5. Testing the System

#### As a User:
1. Navigate to `/events/` to see the events home page
2. Browse upcoming events in the carousel
3. Click "Sign Up" to register for an event
4. View your registered events in "My Events" section
5. Use Google Maps to get directions to events
6. Submit an event proposal via "Organize Event"
7. Check your submissions at "My Submissions"

#### As an Admin:
1. Log in with an admin account
2. Navigate to "Admin Panel" from the dropdown
3. Review pending submissions
4. Approve or reject with notes
5. Create events manually or from approved submissions

### 6. Key Features Implementation

#### Carousel (Image 1):
- Center card is larger (380px vs 280px for side cards)
- Opacity: center = 1, sides = 0.6
- Moves one card at a time with prev/next buttons
- Smooth transitions with CSS transforms

#### Event Signup Form (Image 4):
- HTML5 form validation
- Required fields: Full Name, Email, Phone
- Confirmation checkbox required
- Bootstrap 5 styling

#### My Events with Calendar (Image 3):
- Calendar shows dates with events in orange
- Event list on the left with ellipsis for long titles
- "View More" button opens modal with full details
- "Opt Out" button to cancel registration

#### Event Submission Form (Images 7-9):
- Section 1: Who You Are (organizer info)
- Section 2: Your Event Idea (event details)
- Section 3: Tell Us More (meaningful, experience, accessibility)
- Character counter for summary (max 150 chars)
- HTML5 validation throughout

#### Submission Management (Image 10):
- Full-width cards showing all submission details
- Status badges: Pending Approval (yellow), Approved (green), Rejected (red)
- Edit button (only for pending)
- Delete button
- Admin notes displayed if available

### 7. Navigation Updates

The main home page now has an Events link in the navbar that directs to `/events/`:

```html
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('events.events_home') }}">
        <i class="bi bi-calendar-event"></i> Events
    </a>
</li>
```

### 8. Google Maps Configuration

The system uses:
- User location input with autocomplete
- Event selection dropdown (populated from registered events)
- Travel mode selector (driving/walking/bicycling/transit)
- Directions displayed on map with route

### 9. Status Tracking

Event submissions have three states:
- **Pending**: Awaiting admin review (yellow)
- **Approved**: Accepted by admin (green)
- **Rejected**: Declined by admin (red)

### 10. Responsive Design

The system is fully responsive using Bootstrap 5:
- Mobile-friendly carousel
- Responsive grid layouts
- Touch-friendly buttons
- Optimized for all screen sizes

## Routes Overview

### Public/User Routes:
- `/events/` - Main events page
- `/events/signup/<event_id>` - Sign up for event
- `/events/optout/<event_id>` - Cancel registration
- `/events/submit` - Submit event proposal
- `/events/my-submissions` - View user's submissions
- `/events/submissions/<id>/edit` - Edit submission (pending only)
- `/events/submissions/<id>/delete` - Delete submission

### Admin Routes:
- `/events/admin/submissions` - View all submissions
- `/events/admin/submissions/<id>/review` - Review and approve/reject
- `/events/admin/events/create` - Create new event

## Troubleshooting

### Google Maps not loading:
- Check API key is correct
- Verify APIs are enabled in Google Cloud Console
- Check browser console for errors

### Events not appearing:
- Ensure events table has data
- Check event status is 'upcoming'
- Verify event_date is in the future

### Carousel not moving:
- Check JavaScript is enabled
- Verify Bootstrap 5 JS is loaded
- Check browser console for errors

### Submissions not saving:
- Verify all required fields are filled
- Check database connection
- Review error messages in flash messages

## Notes

- The system uses Bootstrap 5 for UI components
- HTML5 validation is used throughout
- All forms include CSRF protection (via Flask)
- Database queries use parameterized queries for security
- Event images are stored in `static/uploads/events/`
- Default event image: `static/uploads/events/default-event.jpg`

## Sample Data

To test the system, you can insert sample events:

```sql
INSERT INTO events 
(title, description, event_date, start_time, end_time, location, location_address, max_participants, event_type, created_by, status)
VALUES
('Gardening with Grandma', 'Join us for a hands-on gardening day with seniors and youth working side by side in the community garden.', 
 '2025-12-20', '09:00:00', '12:00:00', 'Waterway Point', 'Waterway Point, Singapore 828761', 30, 'Community', 1, 'upcoming'),

('Christmas Chronicles', 'Celebrate the joy of Christmas with us! Look forward to exciting game booths, delicious food, and fun activities.', 
 '2025-12-24', '15:00:00', '20:00:00', 'Community Center', '123 Main Street, Singapore', 100, 'Social', 1, 'upcoming'),

('Shopping Day Out', 'Spend a delightful day out at the mall! Explore a wide variety of stores, enjoy seasonal promotions.',
 '2025-12-28', '11:00:00', '15:00:00', 'Shopping Mall', 'Orchard Road, Singapore', 50, 'Social', 1, 'upcoming');
```

## Contact

For questions or issues, please contact the development team.

---

**Developed with Bootstrap 5, Flask, and Google Maps API**
