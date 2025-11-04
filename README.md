# Ingrasys Lunch Order Bot

## Program Description
This program is a Telegram bot that assists users in setting daily work meal orders and automatically placing orders.  
Main features include:
- Users can set their employee ID and order URL
- Set daily meal types (meat, vegetarian, light meals, etc.)
- Automatically send order API requests at scheduled times
- Query and return this week's menu images
- Display user's current meal settings
- Schedule to periodically fetch index values (`hf_day`) from external ordering system

## Future To-Do List
- [ ] Optimize the SETIU order process
- [ ] Prioritize setting all user employee IDs
- [ ] Adjust scheduled task timing for better notification
- [ ] Add support for vegetarian and special meals in the menu
- [ ] Add error reporting and anomaly monitoring
- [ ] Develop a frontend or web interface for order management

## Log Recording
- The program outputs debugging and status messages using `print()`
- Main logs include network request successes and warnings, and output of ordering parameters
- Can be extended to file logging or more sophisticated logging framework for better traceability


