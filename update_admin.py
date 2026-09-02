import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Admin ka naya email update karein:
cursor.execute("UPDATE users SET email = 'yadavprince773899@gmail.com' WHERE is_admin = 1")

conn.commit()
conn.close()
print("Success: Admin ID updated to yadavprince773899@gmail.com!")
