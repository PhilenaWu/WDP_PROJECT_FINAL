-- Migration: add image_url column to event_submissions
-- Run this once against your MySQL database for the project.

ALTER TABLE event_submissions
ADD COLUMN image_url VARCHAR(255) DEFAULT NULL;
