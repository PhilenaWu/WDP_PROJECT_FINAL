-- Database schema for events functionality

-- Events table (for approved events that appear in carousel)
CREATE TABLE IF NOT EXISTS events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    event_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    location VARCHAR(255) NOT NULL,
    location_address TEXT,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    image_url VARCHAR(255),
    max_participants INT,
    current_participants INT DEFAULT 0,
    event_type VARCHAR(100),
    age_group VARCHAR(50),
    status VARCHAR(50) DEFAULT 'upcoming',
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

-- Event registrations table (users signing up for events)
CREATE TABLE IF NOT EXISTS event_registrations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    user_id INT NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    confirmed BOOLEAN DEFAULT TRUE,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_registration (event_id, user_id)
);

-- Event submissions table (user-submitted events pending approval)
CREATE TABLE IF NOT EXISTS event_submissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    
    -- Organizer info
    organizer_name VARCHAR(255) NOT NULL,
    organizer_dob DATE,
    organizer_age_group VARCHAR(50),
    organizer_email VARCHAR(255) NOT NULL,
    organizer_phone VARCHAR(20) NOT NULL,
    organizer_location VARCHAR(255),
    
    -- Event details
    event_title VARCHAR(255) NOT NULL,
    event_summary TEXT NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    preferred_date DATE NOT NULL,
    expected_participants VARCHAR(50) NOT NULL,
    
    -- Additional info
    why_meaningful TEXT NOT NULL,
    previous_experience TEXT,
    accessibility_considerations TEXT NOT NULL,
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'pending',
    admin_notes TEXT,
    reviewed_by INT,
    reviewed_at TIMESTAMP NULL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
);
