from datetime import datetime, timedelta, time
import pytz
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class MCShiftNotifyWizard(models.TransientModel):
    _name = "mc.shift.notify.wizard"
    _description = "Повідомлення працівникам на завтра (через Inbox + опціонально e-mail)"

    department_id = fields.Many2one("hr.department", string="Відділ")
    employee_ids = fields.Many2many(
        "hr.employee",
        string="Працівники",
        domain=[("user_id", "!=", False)]
    )
    start_time = fields.Float(string="Початок (год)", default=9.0, required=True)
    end_time   = fields.Float(string="Кінець (год)",  default=18.0, required=True)
    message = fields.Text(
        required=True,
        default="Колеги, завтра ви на зміні з {start} до {end}. Якщо є питання — пишіть мені."
    )
    send_email = fields.Boolean(string="Також e-mail", default=False)

    @api.onchange("department_id")
    def _onchange_department(self):
        if self.department_id and not self.employee_ids:
            emps = self.env["hr.employee"].search([
                ("department_id", "=", self.department_id.id),
                ("user_id", "!=", False),
            ])
            self.employee_ids = [(6, 0, emps.ids)]

    def _fmt_time(self, hours):
        h = int(hours); m = int(round((hours - h) * 60))
        return f"{h:02d}:{m:02d}"

    @api.constrains("start_time", "end_time")
    def _check_time_bounds(self):
        for record in self:
            for field_name, value in ("start_time", record.start_time), ("end_time", record.end_time):
                if value is None:
                    continue
                if value < 0 or value >= 24:
                    field_label = record._fields[field_name].string
                    raise UserError(_("Час у полі '{field}' має бути в межах 0-24 годин.").format(field=field_label))
            if record.start_time >= record.end_time:
                raise UserError(_("Кінець зміни має бути пізніше за початок."))

    def _tomorrow_local_bounds(self):
        tzname = self.env.user.tz or "Europe/Kyiv"
        tz = pytz.timezone(tzname)
        now_utc = fields.Datetime.now()
        now_local = fields.Datetime.context_timestamp(self, now_utc)
        tomorrow = (now_local + timedelta(days=1)).date()
        st_h = int(self.start_time); st_m = int(round((self.start_time - st_h) * 60))
        en_h = int(self.end_time);   en_m = int(round((self.end_time - en_h) * 60))
        start_local = tz.localize(datetime.combine(tomorrow, time(st_h, st_m)))
        end_local   = tz.localize(datetime.combine(tomorrow, time(en_h, en_m)))
        if end_local <= start_local:
            raise UserError(_("Кінець зміни має бути пізніше за початок."))
        return start_local, end_local

    def action_notify(self):
        self.ensure_one()
        if not self.employee_ids:
            raise UserError(_("Оберіть хоча б одного працівника або вкажіть відділ."))

        # Підтверджуємо валідність часу та отримуємо часові межі, щоб обробити крайові випадки тайм-зон
        self._tomorrow_local_bounds()

        start_txt = self._fmt_time(self.start_time)
        end_txt   = self._fmt_time(self.end_time)
        body = (self.message or "Ви на зміні завтра {start}-{end}.").format(
            start=start_txt, end=end_txt
        )

        partners = self.employee_ids.mapped("user_id.partner_id")
        if not partners:
            raise UserError(_("Немає жодного партнера з прив'язаним користувачем для вибраних працівників."))

        # Надсилання через Inbox (message_notify) — стабільно на всіх збірках із `mail`
        for p in partners:
            p.message_notify(
                body=body,
                subtype_xmlid="mail.mt_comment",
                partner_ids=[p.id],
                email_layout_xmlid="mail.mail_notification_light",
            )

        # Опційно: e-mail
        if self.send_email:
            for p in partners.filtered(lambda pr: pr.email):
                self.env["mail.mail"].sudo().create({
                    "subject": _("Графік на завтра"),
                    "email_to": p.email,
                    "body_html": f"<p>{body}</p>",
                }).send()

        success_msg = _("Повідомлення надіслано {count} отримувачам через Inbox.").format(
            count=len(partners)
        )
        if self.send_email:
            success_msg += _(" Додатково надіслано e-mail тим, у кого вказана адреса.")
        self.env.user.notify_success(success_msg)

        return {"type": "ir.actions.act_window_close"}
