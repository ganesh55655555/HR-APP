from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash

db = SQLAlchemy()


def create_super_admin():
    admin = User.query.filter_by(role="SUPERADMIN").first()
    if not admin:
        admin = User(
            username="admin",
            email="admin@company.com",
            password_hash=generate_password_hash("admin123"),
            role="SUPERADMIN",
            is_approved=True,
        )
        db.session.add(admin)
        db.session.commit()
        print("Super admin created: admin@company.com / admin123")


# ============================================================
# USER
# ============================================================
class User(UserMixin, db.Model):
    __tablename__ = "users"

    user_id    = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(100), unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role       = db.Column(db.String(20), nullable=False)   # SUPERADMIN | HR | EMPLOYEE
    is_approved = db.Column(db.Boolean, default=False)
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_id(self):
        return str(self.user_id)


# ============================================================
# EMPLOYEE PROFILE  (registration wizard — pending HR approval)
# ============================================================
class EmployeeProfile(db.Model):
    __tablename__ = "employee_profiles"

    profile_id = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.user_id"), unique=True)
    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("profile", uselist=False),
    )

    # Step flags
    step1_done = db.Column(db.Boolean, default=False)
    step2_done = db.Column(db.Boolean, default=False)
    step3_done = db.Column(db.Boolean, default=False)
    step4_done = db.Column(db.Boolean, default=False)
    step5_done = db.Column(db.Boolean, default=False)
    step6_done = db.Column(db.Boolean, default=False)
    submitted  = db.Column(db.Boolean, default=False)

    # DRAFT | PENDING | APPROVED | REJECTED
    status      = db.Column(db.String(20), default="DRAFT")
    hr_remarks  = db.Column(db.Text)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # Step 1 — Personal
    first_name    = db.Column(db.String(100))
    middle_name   = db.Column(db.String(100))
    last_name     = db.Column(db.String(100))
    date_of_birth = db.Column(db.Date)
    gender        = db.Column(db.String(20))
    blood_group   = db.Column(db.String(10))
    religion      = db.Column(db.String(100))
    nationality   = db.Column(db.String(100))
    place_of_birth = db.Column(db.String(200))
    mother_tongue = db.Column(db.String(100))
    marital_status = db.Column(db.String(50))
    personal_email = db.Column(db.String(120))
    mobile_number = db.Column(db.String(20))
    photo_path    = db.Column(db.String(500))

    # Step 2 — Address
    perm_address_line1 = db.Column(db.String(255))
    perm_address_line2 = db.Column(db.String(255))
    perm_city          = db.Column(db.String(100))
    perm_state         = db.Column(db.String(100))
    perm_country       = db.Column(db.String(100))
    perm_postal_code   = db.Column(db.String(20))
    curr_same_as_perm  = db.Column(db.Boolean, default=False)
    curr_address_line1 = db.Column(db.String(255))
    curr_address_line2 = db.Column(db.String(255))
    curr_city          = db.Column(db.String(100))
    curr_state         = db.Column(db.String(100))
    curr_country       = db.Column(db.String(100))
    curr_postal_code   = db.Column(db.String(20))

    # Step 3 — Emergency contacts JSON
    emergency_contacts_json = db.Column(db.Text)

    # Step 4 — Employment
    designation           = db.Column(db.String(150))
    department            = db.Column(db.String(150))
    joining_date          = db.Column(db.Date)
    employment_history_json = db.Column(db.Text)

    # Step 1 — Personal (extended)
    whatsapp_number = db.Column(db.String(20))
    languages_known = db.Column(db.String(500))

    # References (Step 1)
    ref1_name = db.Column(db.String(100))
    ref1_email = db.Column(db.String(120))
    ref1_phone = db.Column(db.String(20))
    ref1_relationship = db.Column(db.String(100))
    ref2_name = db.Column(db.String(100))
    ref2_email = db.Column(db.String(120))
    ref2_phone = db.Column(db.String(20))
    ref2_relationship = db.Column(db.String(100))
    ref3_name = db.Column(db.String(100))
    ref3_email = db.Column(db.String(120))
    ref3_phone = db.Column(db.String(20))
    ref3_relationship = db.Column(db.String(100))

    # Step 5 — Bank & PF
    bank_name      = db.Column(db.String(200))
    account_number = db.Column(db.String(100))
    branch_name    = db.Column(db.String(150))
    ifsc_code      = db.Column(db.String(20))
    pf_number      = db.Column(db.String(100))
    uan_number     = db.Column(db.String(100))
    esi_number     = db.Column(db.String(100))

    # Step 5 — Family Information (JSON for now, persisted during wizard)
    family_info_json = db.Column(db.Text)

    # Step 6 — Documents JSON
    documents_json = db.Column(db.Text)


# ============================================================
# EMPLOYEE  (live, approved record)
# ============================================================
class Employee(db.Model):
    __tablename__ = "employees"

    employee_id  = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.user_id"), unique=True)
    profile_id   = db.Column(db.Integer, db.ForeignKey("employee_profiles.profile_id"))
    employee_code = db.Column(db.String(50), unique=True)

    # Personal
    first_name    = db.Column(db.String(100))
    middle_name   = db.Column(db.String(100))
    last_name     = db.Column(db.String(100))
    date_of_birth = db.Column(db.Date)
    gender        = db.Column(db.String(20))
    blood_group   = db.Column(db.String(10))
    religion      = db.Column(db.String(100))
    nationality   = db.Column(db.String(100))
    place_of_birth = db.Column(db.String(200))
    mother_tongue = db.Column(db.String(100))
    marital_status = db.Column(db.String(50))
    personal_email = db.Column(db.String(120))
    mobile_number = db.Column(db.String(20))
    whatsapp_number = db.Column(db.String(20), nullable=False, default='')
    photo_path    = db.Column(db.String(500))
    languages_known = db.Column(db.String(500))

    # References
    ref1_name = db.Column(db.String(100))
    ref1_email = db.Column(db.String(120))
    ref1_phone = db.Column(db.String(20))
    ref1_relationship = db.Column(db.String(100))
    ref2_name = db.Column(db.String(100))
    ref2_email = db.Column(db.String(120))
    ref2_phone = db.Column(db.String(20))
    ref2_relationship = db.Column(db.String(100))
    ref3_name = db.Column(db.String(100))
    ref3_email = db.Column(db.String(120))
    ref3_phone = db.Column(db.String(20))
    ref3_relationship = db.Column(db.String(100))

    # Employment (HR can edit these directly)
    designation      = db.Column(db.String(150))
    department       = db.Column(db.String(150))
    joining_date     = db.Column(db.Date)
    relieving_date   = db.Column(db.Date)
    employee_status  = db.Column(db.String(20), default="ACTIVE")
    employment_type  = db.Column(db.String(50))   # Full-time | Part-time | Contract
    reporting_manager = db.Column(db.String(150))

    # Address
    perm_address_line1 = db.Column(db.String(255))
    perm_address_line2 = db.Column(db.String(255))
    perm_city          = db.Column(db.String(100))
    perm_state         = db.Column(db.String(100))
    perm_country       = db.Column(db.String(100))
    perm_postal_code   = db.Column(db.String(20))
    curr_address_line1 = db.Column(db.String(255))
    curr_address_line2 = db.Column(db.String(255))
    curr_city          = db.Column(db.String(100))
    curr_state         = db.Column(db.String(100))
    curr_country       = db.Column(db.String(100))
    curr_postal_code   = db.Column(db.String(20))

    # Emergency contacts JSON (copied from profile, stays live)
    emergency_contacts_json = db.Column(db.Text)

    # Bank
    bank_name      = db.Column(db.String(200))
    account_number = db.Column(db.String(100))
    branch_name    = db.Column(db.String(150))
    ifsc_code      = db.Column(db.String(20))

    # PF
    pf_number  = db.Column(db.String(100))
    uan_number = db.Column(db.String(100))
    esi_number = db.Column(db.String(100), nullable=False, default='')

    # Manager Assignment
    manager_id = db.Column(db.Integer, db.ForeignKey("employees.employee_id"), nullable=True)

    # Salary Information (HR only)
    basic_salary = db.Column(db.Numeric(12, 2))
    hra = db.Column(db.Numeric(12, 2))
    allowances = db.Column(db.Numeric(12, 2))
    gross_salary = db.Column(db.Numeric(12, 2))
    ctc = db.Column(db.Numeric(12, 2))  # Cost to Company
    manager = db.relationship(
        "Employee",
        remote_side=[employee_id],
        backref=db.backref("subordinates", uselist=True),
        foreign_keys=[manager_id]
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("employee", uselist=False))
    payslips = db.relationship(
        "EmployeePayslip", backref="employee", cascade="all, delete-orphan",
        order_by="desc(EmployeePayslip.year), desc(EmployeePayslip.month)",
    )
    hr_documents = db.relationship(
        "EmployeeHRDocument", backref="employee", cascade="all, delete-orphan",
        order_by="desc(EmployeeHRDocument.uploaded_at)",
    )
    edit_requests = db.relationship(
        "ProfileEditRequest", backref="employee", cascade="all, delete-orphan",
        order_by="desc(ProfileEditRequest.requested_at)",
    )


# ============================================================
# PAYSLIP
# ============================================================
class EmployeePayslip(db.Model):
    __tablename__ = "employee_payslips"

    payslip_id  = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.employee_id"), nullable=False)
    month       = db.Column(db.Integer, nullable=False)
    year        = db.Column(db.Integer, nullable=False)
    file_path   = db.Column(db.String(500), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("employee_id", "month", "year", name="unique_employee_payslip"),
    )


# ============================================================
# HR-UPLOADED EMPLOYEE DOCUMENTS
# Types: OFFER_LETTER | ASSET_SHEET | EMPLOYMENT_FORM |
#        EXPERIENCE_LETTER | RELIEVING_LETTER | FULL_FINAL
# ============================================================
class EmployeeHRDocument(db.Model):
    __tablename__ = "employee_hr_documents"

    doc_id      = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.employee_id"), nullable=False)
    doc_type    = db.Column(db.String(50), nullable=False)
    label       = db.Column(db.String(200))          # optional display name
    file_path   = db.Column(db.String(500), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes       = db.Column(db.Text)

    uploader = db.relationship("User", foreign_keys=[uploaded_by])


# ============================================================
# PROFILE EDIT REQUEST  (employee requests a change → HR approves)
# ============================================================
class ProfileEditRequest(db.Model):
    __tablename__ = "profile_edit_requests"

    request_id  = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.employee_id"), nullable=False)

    # JSON blob of {field: new_value}
    changes_json = db.Column(db.Text, nullable=False)

    # PENDING | APPROVED | REJECTED
    status       = db.Column(db.String(20), default="PENDING")
    reason       = db.Column(db.Text)           # why employee wants the change
    hr_remarks   = db.Column(db.Text)
    reviewed_by  = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    reviewed_at  = db.Column(db.DateTime, nullable=True)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviewer = db.relationship("User", foreign_keys=[reviewed_by])


# ============================================================
# AUDIT LOG
# ============================================================
class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    audit_id     = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    action       = db.Column(db.String(200))
    target_table = db.Column(db.String(100))
    target_id    = db.Column(db.Integer)
    details      = db.Column(db.Text)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="audit_logs")


# ============================================================
# EMPLOYEE FAMILY INFORMATION
# ============================================================
class EmployeeFamily(db.Model):
    __tablename__ = "employee_family"

    family_id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.employee_id"), unique=True, nullable=False)
    mother_name = db.Column(db.String(100), nullable=False)
    father_name = db.Column(db.String(100), nullable=False)
    spouse_name = db.Column(db.String(100))
    epf_member = db.Column(db.Boolean, nullable=False, default=False)
    family_pension_scheme = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee = db.relationship("Employee", backref=db.backref("family_info", uselist=False))


# ============================================================
# EMPLOYEE ASSET DETAILS (Access, Phone, Bike Card)
# ============================================================
class EmployeeAsset(db.Model):
    __tablename__ = "employee_asset"

    asset_id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.employee_id"), unique=True, nullable=False)
    access_office_field_1 = db.Column(db.String(255), nullable=False)
    access_office_field_2 = db.Column(db.String(255), nullable=False)
    access_office_field_3 = db.Column(db.String(255), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    bike_access_card_number = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee = db.relationship("Employee", backref=db.backref("asset_info", uselist=False))


# ============================================================
# EMPLOYEE CONTRACT
# ============================================================
class EmployeeContract(db.Model):
    __tablename__ = "employee_contract"

    contract_id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.employee_id"), nullable=False)
    contract_type = db.Column(db.String(50), nullable=False)  # OFFER, RENEWAL, AMENDMENT, etc.
    file_path = db.Column(db.String(500))  # Path to uploaded contract file
    contract_details_json = db.Column(db.Text)  # Structured contract terms
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)  # NULL for permanent
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.user_id"))

    employee = db.relationship("Employee", backref=db.backref("contracts", uselist=True))
    creator = db.relationship("User", foreign_keys=[created_by])
