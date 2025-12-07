-- SQLite Schema for BuyMe application

DROP TABLE IF EXISTS bid;
DROP TABLE IF EXISTS auctions;
DROP TABLE IF EXISTS item;
DROP TABLE IF EXISTS category;
DROP TABLE IF EXISTS user;

-- User table (singular to match your code)
CREATE TABLE user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    f_name VARCHAR(50),
    l_name VARCHAR(50),
    email VARCHAR(255),
    user_type VARCHAR(20) NOT NULL CHECK(user_type IN ('customer', 'representative', 'admin'))
);
-- insert sample user
INSERT INTO user (username, password, f_name, l_name, user_type) VALUES 
('admin', 'admin', 'Admin', 'Admin', 'admin');
INSERT INTO user (username, password, f_name, l_name, user_type) VALUES 
('customer', 'customer', 'Customer', 'Customer', 'customer');
INSERT INTO user (username, password, f_name, l_name, user_type) VALUES 
('representative', 'representative', 'Representative', 'Representative', 'representative');

-- Category table
CREATE TABLE category (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name VARCHAR(100) NOT NULL
);
INSERT INTO category (category_name) VALUES 
('Electronics'),
('Laptops'),
('Gaming Laptops'),
('Phones'),
('Cameras');

-- Item table
CREATE TABLE item (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name VARCHAR(255) NOT NULL,
    item_desc TEXT,
    category_id INTEGER NOT NULL,
    FOREIGN KEY (category_id) REFERENCES category(category_id)
);

-- Add sample items
INSERT INTO item (item_name, item_desc, category_id) VALUES 
('MacBook Air M4', "random description macbook", 2);

INSERT INTO item (item_name, item_desc, category_id)
VALUES ('iPhone 16', "random description iphone16", 4);



-- Category-specific detail types (defines what details exist for each category)
-- Laptop : CPU, Memory, Disk (would contain 3 rows in category_detail_type)
-- Phone: Display, Battery, Camera, Storage
CREATE TABLE category_detail_type (
    detail_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    detail_name VARCHAR(100) NOT NULL,
    FOREIGN KEY (category_id) REFERENCES category(category_id)
);

-- insert sample category details for Laptops
-- For category 'Laptop', define what details it has
INSERT INTO category_detail_type (category_id, detail_name)
VALUES 
(2, 'CPU'),
(2, 'Memory'),
(2, 'Disk');

-- for category 'Phones' define detail types
INSERT INTO category_detail_type (category_id, detail_name)
VALUES
(4, 'Display'),
(4, 'Battery'),
(4, 'Camera'),
(4, 'Storage');

-- Actual item details (stores values for each item/detail pair)
CREATE TABLE item_detail (
    item_detail_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    detail_type_id INTEGER NOT NULL,
    detail_value VARCHAR(255),
    FOREIGN KEY (item_id) REFERENCES item(item_id),
    FOREIGN KEY (detail_type_id) REFERENCES category_detail_type(detail_type_id)
);

-- Add sample item (macbook) details (cpu, memory, disk)
INSERT INTO item_detail (item_id, detail_type_id, detail_value)
VALUES
(1, 1, 'Apple M4 Chip'),  -- CPU
(1, 2, '16GB'),           -- Memory
(1, 3, '512GB SSD');      -- Disk

-- add iphone 16 specific details
INSERT INTO item_detail (item_id, detail_type_id, detail_value)
VALUES
(2, 4, '6.3-inch OLED 120Hz'),
(2, 5, '4350 mAh'),
(2, 6, '48MP Dual Camera'),
(2, 7, '256GB');


-- Auctions table
CREATE TABLE auctions (
    auction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    auction_title VARCHAR(255) NOT NULL DEFAULT "",
    auction_desc TEXT NOT NULL DEFAULT "",
    item_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    starting_price DECIMAL(12,2) NOT NULL,
    auction_start DATETIME NOT NULL,
    auction_end DATETIME NOT NULL,
    current_highest_bid DECIMAL(12,2) DEFAULT 0,
    FOREIGN KEY (item_id) REFERENCES item(item_id),
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- insert sample auction (sold by admin and customer)
INSERT INTO auctions (item_id, auction_title, auction_desc, user_id, starting_price, auction_start, auction_end) VALUES 
(1, 'Selling mint condition MacBook Air M4!!', 'This MacBook Air M4 is in mint condition, with no scratches or dents. It has a beautiful display and a fast processor.', 1, 1000.00, '2025-10-01 10:00:00', '2025-11-01 11:00:00');
INSERT INTO auctions (item_id, auction_title, auction_desc, user_id, starting_price, auction_start, auction_end) VALUES 
(2, 'Selling mint condition iPhone 16!!', 'This iPhone 16 is in mint condition, with no scratches or dents. It has a beautiful display and a fast processor.', 2, 1000.00, '2025-11-01 10:00:00', '2025-12-01 11:00:00');

-- Bid table
CREATE TABLE bid (
    bid_id INTEGER PRIMARY KEY AUTOINCREMENT,
    auction_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    bid_price DECIMAL(12,2) NOT NULL,
    bid_status VARCHAR(20) NOT NULL CHECK(bid_status IN ('PLACED','LEADING','OUTBID','RETRACTED','INVALID','WON','LOST')),
    auction_bid_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (auction_id) REFERENCES auctions(auction_id),
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- Forum tables for Q&A between users and customer representatives
CREATE TABLE forum_question (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

CREATE TABLE forum_answer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    rep_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES forum_question(id),
    FOREIGN KEY (rep_id) REFERENCES user(id)
);
