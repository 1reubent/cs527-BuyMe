# BuyMe Project Checklist

- [ ] **Customer Home View**

  - [ ] **"My Alerts" View**
    - [ ] My Alerts button — redirects to Alerts view (could be placed in “My Profile”?)
  - [x] **Create a New Auction Button** (right of header)
    - [x] Item sections with category dropdown; item details fields change based on category
      - [x] Add table for `item_category_details` (each category has unique fields)
  - [x] **My Profile** (in navigation)
    - [x] Redirects to User Profile View
    - [x] Delete account functionality
  - [x] **Search Field**
    - [x] Text box | "Looking for…" dropdown (user, auction) | Active/inactive toggle?
    - [ ] On search, go to SearchView
      - [ ] Add “Show Filters” button on home page
  - [x] **List of Current Auctions** (left column)
  - [ ] **Partial List of Users** (right column)
    - Click to “View All” (goes to User Search View)

- [ ] **Search View**

  - [ ] More specific filters:
    - [ ] **Auctions**: category filter, dynamic detail filter, seller name/username/type, item name, category, category-based details
    - [ ] **Users**: search by name, username, type

- [x] **User Profile View** (viewable to everyone?)

  - [x] Auctions you're selling (My Auctions)
  - [x] Auctions you participated in
  - [ ] My Alerts?

- [ ] **Auction View**

  - [ ] View item info, seller info, highest bid, recent bidders
  - [ ] View bid history
  - [ ] Show similar items listed within the past month (recommended section)

- [ ] **Customer Representative View**

  - [ ] Search for users
  - [ ] Modify user information (username, password, email)
  - [ ] Access forum where users ask questions and reps can answer

- [ ] **Admin View**

  - [ ] Add/delete item categories
    - [ ] Define category detail types when creating categories
  - [ ] Create Customer Representative accounts

  - [ ] Generate Summary Sales Reports
    - [ ] Should include: total earnings; earnings per item, item type, end-user; best-selling items and best-selling end-users
