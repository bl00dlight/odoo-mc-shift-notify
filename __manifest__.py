{
    "name": "MC Shift Notify",
    "version": "18.0.1.0.4",
    "summary": "Повідомлення працівникам про завтрашню зміну (універсально через Inbox + опціонально e-mail)",
    "author": "MC",
    "license": "LGPL-3",
    "depends": ["hr", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/shift_notify_views.xml"
    ],
    "installable": True,
    "application": False
}
