import json
import os
from datetime import datetime

from flask import (
    render_template, request, redirect, url_for,
    flash, current_app, send_from_directory, abort
)
from flask_login import login_required, current_user

from app import app
from sql import db, User, Employee, EmployeeProfile, EmployeePayslip, \
    EmployeeHRDocument, ProfileEditRequest, AuditLog, EmployeeFamily, EmployeeAsset, EmployeeContract
from utils import role_required, save_upload, log_action

HR_DOC_TYPES = [
    ("OFFER_LETTER",      "Offer Letter"),
    ("ASSET_SHEET",       "Asset Sheet"),
    ("EMPLOYMENT_FORM",   "Employment Form"),
    ("EXPERIENCE_LETTER", "Experience Letter"),
    ("RELIEVING_LETTER",  "Relieving Letter"),
    ("FULL_FINAL",        "Full & Final Settlement"),
]
HR_DOC_MAP = dict(HR_DOC_TYPES)

MONTHS = [
    (1,"January"),(2,"February"),(3,"March"),(4,"April"),
    (5,"May"),(6,"June"),(7,"July"),(8,"August"),
    (9,"September"),(10,"October"),(11,"November"),(12,"December"),
]


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/hr/dashboard")
@login_required
@role_required("HR")
def hr_dashboard():
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "active")  # active | left | all

    pending  = EmployeeProfile.query.filter_by(status="PENDING").all()
    approved = EmployeeProfile.query.filter_by(status="APPROVED").all()
    rejected = EmployeeProfile.query.filter_by(status="REJECTED").all()

    # Employee search with status filter
    emp_results = None
    if q:
        query = Employee.query.filter(
            (Employee.first_name.ilike(f"%{q}%")) |
            (Employee.last_name.ilike(f"%{q}%"))  |
            (Employee.employee_code.ilike(f"%{q}%")) |
            (Employee.department.ilike(f"%{q}%"))  |
            (Employee.designation.ilike(f"%{q}%"))
        )

        # Apply status filter
        if status_filter == "active":
            query = query.filter(Employee.employee_status == "ACTIVE")
        elif status_filter == "left":
            query = query.filter(Employee.employee_status == "LEFT")
        # "all" shows both

        emp_results = query.all()

    pending_edit_requests = ProfileEditRequest.query.filter_by(status="PENDING").count()

    return render_template(
        "hr_dashboard.html",
        pending=pending,
        approved=approved,
        rejected=rejected,
        emp_results=emp_results,
        search_query=q,
        status_filter=status_filter,
        pending_edit_requests=pending_edit_requests,
    )


# ── Profile review / approve / reject ─────────────────────────────────────────

@app.route("/hr/profile/<int:profile_id>")
@login_required
@role_required("HR")
def hr_view_profile(profile_id):
    profile = EmployeeProfile.query.get_or_404(profile_id)
    ec      = json.loads(profile.emergency_contacts_json or "[]")
    history = json.loads(profile.employment_history_json or "[]")
    docs    = json.loads(profile.documents_json or "[]")
    return render_template(
        "hr_view_profile.html",
        profile=profile, emergency_contacts=ec,
        employment_history=history, documents=docs,
    )


@app.route("/hr/profile/<int:profile_id>/approve", methods=["POST"])
@login_required
@role_required("HR")
def hr_approve_profile(profile_id):
    profile = EmployeeProfile.query.get_or_404(profile_id)
    if profile.status != "PENDING":
        flash("Profile is not in pending state.", "warning")
        return redirect(url_for("hr_view_profile", profile_id=profile_id))

    profile.status      = "APPROVED"
    profile.hr_remarks  = request.form.get("remarks", "").strip()
    profile.reviewed_by = current_user.user_id
    profile.reviewed_at = datetime.utcnow()

    employee = Employee.query.filter_by(user_id=profile.user_id).first()
    if not employee:
        count    = Employee.query.count() + 1
        emp_code = f"EMP{count:04d}"
        employee = Employee(
            user_id=profile.user_id, profile_id=profile.profile_id,
            employee_code=emp_code,
            first_name=profile.first_name, middle_name=profile.middle_name,
            last_name=profile.last_name, date_of_birth=profile.date_of_birth,
            gender=profile.gender, blood_group=profile.blood_group,
            religion=profile.religion, nationality=profile.nationality,
            place_of_birth=profile.place_of_birth, mother_tongue=profile.mother_tongue,
            marital_status=profile.marital_status, personal_email=profile.personal_email,
            mobile_number=profile.mobile_number, whatsapp_number=profile.whatsapp_number,
            photo_path=profile.photo_path,
            languages_known=profile.languages_known,
            ref1_name=profile.ref1_name, ref1_email=profile.ref1_email,
            ref1_phone=profile.ref1_phone, ref1_relationship=profile.ref1_relationship,
            ref2_name=profile.ref2_name, ref2_email=profile.ref2_email,
            ref2_phone=profile.ref2_phone, ref2_relationship=profile.ref2_relationship,
            ref3_name=profile.ref3_name, ref3_email=profile.ref3_email,
            ref3_phone=profile.ref3_phone, ref3_relationship=profile.ref3_relationship,
            designation=profile.designation, department=profile.department,
            joining_date=profile.joining_date,
            perm_address_line1=profile.perm_address_line1,
            perm_address_line2=profile.perm_address_line2,
            perm_city=profile.perm_city, perm_state=profile.perm_state,
            perm_country=profile.perm_country, perm_postal_code=profile.perm_postal_code,
            curr_address_line1=profile.curr_address_line1,
            curr_address_line2=profile.curr_address_line2,
            curr_city=profile.curr_city, curr_state=profile.curr_state,
            curr_country=profile.curr_country, curr_postal_code=profile.curr_postal_code,
            emergency_contacts_json=profile.emergency_contacts_json,
            bank_name=profile.bank_name, account_number=profile.account_number,
            branch_name=profile.branch_name, ifsc_code=profile.ifsc_code,
            pf_number=profile.pf_number, uan_number=profile.uan_number,
            esi_number=profile.esi_number,
        )
        db.session.add(employee)

        family_info = json.loads(profile.family_info_json or "{}")
        if family_info.get("mother_name") or family_info.get("father_name"):
            family = EmployeeFamily(
                employee=employee,
                mother_name=family_info.get("mother_name", ""),
                father_name=family_info.get("father_name", ""),
                spouse_name=family_info.get("spouse_name", ""),
                epf_member=family_info.get("epf_member", False),
                family_pension_scheme=family_info.get("family_pension_scheme", ""),
            )
            db.session.add(family)

        asset = EmployeeAsset(
            employee=employee,
            access_office_field_1="",
            access_office_field_2="",
            access_office_field_3="",
            phone_number="",
            bike_access_card_number="",
        )
        db.session.add(asset)

    db.session.commit()
    log_action(current_user.user_id, "APPROVE_PROFILE", "employee_profiles", profile_id,
               f"Approved profile user_id={profile.user_id}")
    flash(f"Profile approved — Employee code: {employee.employee_code}", "success")
    return redirect(url_for("hr_dashboard"))


@app.route("/hr/profile/<int:profile_id>/reject", methods=["POST"])
@login_required
@role_required("HR")
def hr_reject_profile(profile_id):
    profile = EmployeeProfile.query.get_or_404(profile_id)
    remarks = request.form.get("remarks", "").strip()
    if not remarks:
        flash("Rejection remarks are required.", "danger")
        return redirect(url_for("hr_view_profile", profile_id=profile_id))

    profile.status      = "REJECTED"
    profile.hr_remarks  = remarks
    profile.reviewed_by = current_user.user_id
    profile.reviewed_at = datetime.utcnow()
    db.session.commit()
    log_action(current_user.user_id, "REJECT_PROFILE", "employee_profiles", profile_id, remarks)
    flash("Profile rejected.", "warning")
    return redirect(url_for("hr_dashboard"))


# ── HR Edit Employee ───────────────────────────────────────────────────────────

@app.route("/hr/employee/<int:employee_id>")
@login_required
@role_required("HR")
def hr_view_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    ec       = json.loads(employee.emergency_contacts_json or "[]")
    payslips = (EmployeePayslip.query
                .filter_by(employee_id=employee_id)
                .order_by(EmployeePayslip.year.desc(), EmployeePayslip.month.desc())
                .all())
    hr_docs  = EmployeeHRDocument.query.filter_by(employee_id=employee_id)\
                .order_by(EmployeeHRDocument.uploaded_at.desc()).all()
    edit_requests = ProfileEditRequest.query.filter_by(employee_id=employee_id)\
                    .order_by(ProfileEditRequest.requested_at.desc()).all()
    return render_template(
        "hr_employee_detail.html",
        employee=employee, emergency_contacts=ec,
        payslips=payslips, hr_docs=hr_docs,
        hr_doc_types=HR_DOC_TYPES, hr_doc_map=HR_DOC_MAP,
        edit_requests=edit_requests,
        months=MONTHS,
        current_year=datetime.utcnow().year,
        years=list(range(datetime.utcnow().year - 3, datetime.utcnow().year + 2)),
    )


@app.route("/hr/employee/<int:employee_id>/mark-left", methods=["POST"])
@login_required
@role_required("HR", "ADMIN")
def hr_mark_employee_left(employee_id):
    employee = Employee.query.get_or_404(employee_id)

    if employee.employee_status == "LEFT":
        flash("Employee is already marked as left.", "info")
        return redirect(url_for("hr_view_employee", employee_id=employee_id))

    relieving_date_str = request.form.get("relieving_date", "").strip()
    remarks = request.form.get("remarks", "").strip()

    if not relieving_date_str:
        flash("Relieving date is required.", "danger")
        return redirect(url_for("hr_view_employee", employee_id=employee_id))

    try:
        relieving_date = datetime.strptime(relieving_date_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid relieving date format.", "danger")
        return redirect(url_for("hr_view_employee", employee_id=employee_id))

    employee.employee_status = "LEFT"
    employee.relieving_date = relieving_date

    db.session.commit()
    log_action(
        current_user.user_id,
        "MARK_EMPLOYEE_LEFT",
        "employees",
        employee_id,
        f"Marked as LEFT on {relieving_date}. Remarks: {remarks}"
    )

    flash(f"Employee {employee.first_name} {employee.last_name} marked as LEFT on {relieving_date}.", "success")
    return redirect(url_for("hr_view_employee", employee_id=employee_id))


@app.route("/hr/employee/<int:employee_id>/mark-active", methods=["POST"])
@login_required
@role_required("HR", "ADMIN")
def hr_mark_employee_active(employee_id):
    employee = Employee.query.get_or_404(employee_id)

    if employee.employee_status == "ACTIVE":
        flash("Employee is already active.", "info")
        return redirect(url_for("hr_view_employee", employee_id=employee_id))

    employee.employee_status = "ACTIVE"
    employee.relieving_date = None

    db.session.commit()
    log_action(
        current_user.user_id,
        "MARK_EMPLOYEE_ACTIVE",
        "employees",
        employee_id,
        "Marked as ACTIVE (rejoined)"
    )

    flash(f"Employee {employee.first_name} {employee.last_name} marked as ACTIVE.", "success")
    return redirect(url_for("hr_view_employee", employee_id=employee_id))


@app.route("/hr/employee/<int:employee_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("HR")
def hr_edit_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)

    if request.method == "POST":
        f = request.form
        # HR can edit any field directly (no approval needed for HR edits)
        employee.first_name     = f.get("first_name", employee.first_name)
        employee.middle_name    = f.get("middle_name", employee.middle_name)
        employee.last_name      = f.get("last_name", employee.last_name)
        employee.gender         = f.get("gender", employee.gender)
        employee.blood_group    = f.get("blood_group", employee.blood_group)
        employee.nationality    = f.get("nationality", employee.nationality)
        employee.religion       = f.get("religion", employee.religion)
        employee.marital_status = f.get("marital_status", employee.marital_status)
        employee.mobile_number  = f.get("mobile_number", employee.mobile_number)
        employee.whatsapp_number = f.get("whatsapp_number", employee.whatsapp_number)
        employee.personal_email = f.get("personal_email", employee.personal_email)
        employee.designation    = f.get("designation", employee.designation)
        employee.department     = f.get("department", employee.department)
        employee.employment_type = f.get("employment_type", employee.employment_type)
        employee.reporting_manager = f.get("reporting_manager", employee.reporting_manager)
        jd = f.get("joining_date")
        employee.joining_date   = datetime.strptime(jd, "%Y-%m-%d").date() if jd else employee.joining_date
        rd = f.get("relieving_date")
        employee.relieving_date = datetime.strptime(rd, "%Y-%m-%d").date() if rd else None
        employee.perm_address_line1 = f.get("perm_address_line1", employee.perm_address_line1)
        employee.perm_address_line2 = f.get("perm_address_line2", employee.perm_address_line2)
        employee.perm_city      = f.get("perm_city", employee.perm_city)
        employee.perm_state     = f.get("perm_state", employee.perm_state)
        employee.perm_country   = f.get("perm_country", employee.perm_country)
        employee.perm_postal_code = f.get("perm_postal_code", employee.perm_postal_code)
        employee.curr_address_line1 = f.get("curr_address_line1", employee.curr_address_line1)
        employee.curr_address_line2 = f.get("curr_address_line2", employee.curr_address_line2)
        employee.curr_city      = f.get("curr_city", employee.curr_city)
        employee.curr_state     = f.get("curr_state", employee.curr_state)
        employee.curr_country   = f.get("curr_country", employee.curr_country)
        employee.curr_postal_code = f.get("curr_postal_code", employee.curr_postal_code)
        employee.bank_name      = f.get("bank_name", employee.bank_name)
        employee.account_number = f.get("account_number", employee.account_number)
        employee.branch_name    = f.get("branch_name", employee.branch_name)
        employee.ifsc_code      = f.get("ifsc_code", employee.ifsc_code)
        employee.pf_number      = f.get("pf_number", employee.pf_number)
        employee.uan_number     = f.get("uan_number", employee.uan_number)
        employee.esi_number     = f.get("esi_number", employee.esi_number)

        # Photo update
        photo = request.files.get("photo")
        if photo and photo.filename:
            path = save_upload(photo, "photos")
            if path:
                employee.photo_path = path

        # Emergency contacts
        names  = f.getlist("ec_name")
        rels   = f.getlist("ec_relationship")
        phones = f.getlist("ec_phone")
        contacts = [
            {"name": n.strip(), "relationship": r.strip(), "phone": p.strip()}
            for n, r, p in zip(names, rels, phones) if n.strip()
        ]
        employee.emergency_contacts_json = json.dumps(contacts)

        employee.updated_at = datetime.utcnow()
        db.session.commit()
        log_action(current_user.user_id, "HR_EDIT_EMPLOYEE", "employees", employee_id,
                   f"HR edited employee {employee.employee_code}")
        flash("Employee information updated.", "success")
        return redirect(url_for("hr_view_employee", employee_id=employee_id))

    ec = json.loads(employee.emergency_contacts_json or "[]")
    return render_template("hr_edit_employee.html", employee=employee, emergency_contacts=ec)


# ── Edit-request review (employee-submitted change requests) ──────────────────

@app.route("/hr/edit-requests")
@login_required
@role_required("HR")
def hr_edit_requests():
    pending = ProfileEditRequest.query.filter_by(status="PENDING")\
              .order_by(ProfileEditRequest.requested_at.desc()).all()
    return render_template("hr_edit_requests.html", requests=pending)


@app.route("/hr/edit-request/<int:req_id>/approve", methods=["POST"])
@login_required
@role_required("HR")
def hr_approve_edit(req_id):
    req = ProfileEditRequest.query.get_or_404(req_id)
    employee = Employee.query.get(req.employee_id)
    if not employee:
        abort(404)

    changes = json.loads(req.changes_json)
    for field, value in changes.items():
        if hasattr(employee, field):
            # handle date fields
            if field in ("date_of_birth", "joining_date", "relieving_date") and value:
                try:
                    value = datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError:
                    pass
            setattr(employee, field, value)

    employee.updated_at = datetime.utcnow()
    req.status      = "APPROVED"
    req.hr_remarks  = request.form.get("remarks", "")
    req.reviewed_by = current_user.user_id
    req.reviewed_at = datetime.utcnow()
    db.session.commit()
    log_action(current_user.user_id, "APPROVE_EDIT_REQUEST", "profile_edit_requests", req_id)
    flash("Changes approved and applied.", "success")
    return redirect(url_for("hr_edit_requests"))


@app.route("/hr/edit-request/<int:req_id>/reject", methods=["POST"])
@login_required
@role_required("HR")
def hr_reject_edit(req_id):
    req = ProfileEditRequest.query.get_or_404(req_id)
    req.status      = "REJECTED"
    req.hr_remarks  = request.form.get("remarks", "No reason given.")
    req.reviewed_by = current_user.user_id
    req.reviewed_at = datetime.utcnow()
    db.session.commit()
    flash("Edit request rejected.", "warning")
    return redirect(url_for("hr_edit_requests"))


# ── Payslip Management ────────────────────────────────────────────────────────

@app.route("/hr/payslips")
@login_required
@role_required("HR")
def hr_payslips():
    q = request.args.get("q", "").strip()
    emp_q = Employee.query.filter_by(employee_status="ACTIVE")
    if q:
        emp_q = emp_q.filter(
            (Employee.first_name.ilike(f"%{q}%")) |
            (Employee.last_name.ilike(f"%{q}%"))  |
            (Employee.employee_code.ilike(f"%{q}%"))
        )
    employees = emp_q.all()
    return render_template("hr_payslips.html", employees=employees, search_query=q)


@app.route("/hr/payslip/upload/<int:employee_id>", methods=["GET", "POST"])
@login_required
@role_required("HR")
def hr_upload_payslip(employee_id):
    employee = Employee.query.get_or_404(employee_id)

    if request.method == "POST":
        month = request.form.get("month", type=int)
        year  = request.form.get("year",  type=int)
        payslip_file = request.files.get("payslip_file")

        if not all([month, year, payslip_file]) or payslip_file.filename == "":
            flash("Month, year and file are all required.", "danger")
            return redirect(request.url)

        path = save_upload(payslip_file, "payslips")
        if not path:
            flash("Invalid file type. PDF, PNG, JPG only.", "danger")
            return redirect(request.url)

        existing = EmployeePayslip.query.filter_by(
            employee_id=employee_id, month=month, year=year).first()
        if existing:
            _delete_file(existing.file_path)
            existing.file_path   = path
            existing.uploaded_by = current_user.user_id
            existing.uploaded_at = datetime.utcnow()
        else:
            db.session.add(EmployeePayslip(
                employee_id=employee_id, month=month, year=year,
                file_path=path, uploaded_by=current_user.user_id,
            ))
        db.session.commit()
        log_action(current_user.user_id, "UPLOAD_PAYSLIP", "employee_payslips",
                   employee_id, f"Payslip {month}/{year}")
        flash(f"Payslip {month}/{year} uploaded.", "success")
        return redirect(url_for("hr_view_employee", employee_id=employee_id))

    all_payslips = (EmployeePayslip.query.filter_by(employee_id=employee_id)
                    .order_by(EmployeePayslip.year.desc(), EmployeePayslip.month.desc()).all())
    cur_yr = datetime.utcnow().year
    return render_template(
        "hr_upload_payslip.html", employee=employee,
        all_payslips=all_payslips, months=MONTHS,
        years=list(range(cur_yr - 3, cur_yr + 2)),
    )


@app.route("/hr/payslip/delete/<int:payslip_id>", methods=["POST"])
@login_required
@role_required("HR")
def hr_delete_payslip(payslip_id):
    ps = EmployeePayslip.query.get_or_404(payslip_id)
    employee_id = ps.employee_id
    _delete_file(ps.file_path)
    db.session.delete(ps)
    db.session.commit()
    flash("Payslip deleted.", "info")
    return redirect(url_for("hr_view_employee", employee_id=employee_id))


# ── HR Document Upload / Delete / Download ────────────────────────────────────

@app.route("/hr/employee/<int:employee_id>/doc/upload", methods=["POST"])
@login_required
@role_required("HR")
def hr_upload_doc(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    doc_type = request.form.get("doc_type")
    label    = request.form.get("label", "").strip()
    notes    = request.form.get("notes", "").strip()
    doc_file = request.files.get("doc_file")

    if not doc_type or not doc_file or doc_file.filename == "":
        flash("Document type and file are required.", "danger")
        return redirect(url_for("hr_view_employee", employee_id=employee_id))

    path = save_upload(doc_file, f"hr_docs/{employee_id}")
    if not path:
        flash("Invalid file type. PDF, PNG, JPG only.", "danger")
        return redirect(url_for("hr_view_employee", employee_id=employee_id))

    doc = EmployeeHRDocument(
        employee_id=employee_id, doc_type=doc_type,
        label=label or HR_DOC_MAP.get(doc_type, doc_type),
        file_path=path, uploaded_by=current_user.user_id, notes=notes,
    )
    db.session.add(doc)
    db.session.commit()
    log_action(current_user.user_id, "UPLOAD_HR_DOC", "employee_hr_documents",
               employee_id, f"{doc_type} for {employee.employee_code}")
    flash(f"{HR_DOC_MAP.get(doc_type, doc_type)} uploaded.", "success")
    return redirect(url_for("hr_view_employee", employee_id=employee_id))


@app.route("/hr/employee/doc/delete/<int:doc_id>", methods=["POST"])
@login_required
@role_required("HR")
def hr_delete_doc(doc_id):
    doc = EmployeeHRDocument.query.get_or_404(doc_id)
    employee_id = doc.employee_id
    _delete_file(doc.file_path)
    db.session.delete(doc)
    db.session.commit()
    flash("Document deleted.", "info")
    return redirect(url_for("hr_view_employee", employee_id=employee_id))


@app.route("/hr/employee/doc/download/<int:doc_id>")
@login_required
@role_required("HR", "EMPLOYEE", "SUPERADMIN")
def download_hr_doc(doc_id):
    doc = EmployeeHRDocument.query.get_or_404(doc_id)

    # Employees can only download their own docs
    if current_user.role == "EMPLOYEE":
        emp = Employee.query.filter_by(user_id=current_user.user_id).first()
        if not emp or emp.employee_id != doc.employee_id:
            abort(403)

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    full_path = os.path.join(upload_folder, doc.file_path)
    return send_from_directory(
        os.path.dirname(full_path),
        os.path.basename(full_path),
        as_attachment=True,
    )


# ── Helper ────────────────────────────────────────────────────────────────────

def _delete_file(relative_path):
    from flask import current_app
    if relative_path:
        full = os.path.join(current_app.config["UPLOAD_FOLDER"], relative_path)
        if os.path.exists(full):
            os.remove(full)


# ── Manager, Family, Asset & Contract Management ───────────────────────────────

@app.route("/hr/employee/<int:employee_id>/edit-hr-info", methods=["GET", "POST"])
@login_required
@role_required("HR")
def hr_edit_employee_info(employee_id):
    """HR can edit: Manager, Salary, Contract, Documents"""
    employee = Employee.query.get_or_404(employee_id)

    if request.method == "POST":
        f = request.form

        # Manager Assignment
        manager_id = f.get("manager_id", type=int) or None
        if manager_id:
            manager = Employee.query.filter_by(employee_id=manager_id).first()
            if manager:
                employee.manager_id = manager_id
            else:
                flash("Selected manager not found.", "danger")
                return redirect(request.url)
        else:
            employee.manager_id = None

        # Salary Information
        try:
            basic_salary = f.get("basic_salary", "").strip()
            hra = f.get("hra", "").strip()
            allowances = f.get("allowances", "").strip()

            if basic_salary:
                employee.basic_salary = float(basic_salary)
            if hra:
                employee.hra = float(hra)
            if allowances:
                employee.allowances = float(allowances)

            # Calculate gross salary and CTC
            if employee.basic_salary:
                gross = (employee.basic_salary or 0) + (employee.hra or 0) + (employee.allowances or 0)
                employee.gross_salary = gross
                employee.ctc = gross  # CTC = Gross for now, can add other components later
        except ValueError:
            flash("Invalid salary amount. Please enter valid numbers.", "danger")
            return redirect(request.url)

        # Contract Management
        contract_type = f.get("contract_type", "").strip()
        if contract_type:
            contract_start = f.get("contract_start")
            if contract_start:
                try:
                    start_date = datetime.strptime(contract_start, "%Y-%m-%d").date()
                    contract = EmployeeContract(
                        employee_id=employee_id,
                        contract_type=contract_type,
                        start_date=start_date,
                        created_by=current_user.user_id,
                    )

                    contract_end = f.get("contract_end")
                    if contract_end:
                        contract.end_date = datetime.strptime(contract_end, "%Y-%m-%d").date()

                    contract_file = request.files.get("contract_file")
                    if contract_file and contract_file.filename:
                        path = save_upload(contract_file, f"contracts")
                        if path:
                            contract.file_path = path

                    db.session.add(contract)
                except ValueError:
                    flash("Invalid contract date format.", "danger")
                    return redirect(request.url)

        employee.updated_at = datetime.utcnow()
        db.session.commit()
        log_action(current_user.user_id, "HR_EDIT_EMPLOYEE_INFO", "employees", employee_id,
                   f"Updated manager, salary, contract for {employee.employee_code}")
        flash("Manager, salary, and contract information updated successfully.", "success")
        return redirect(url_for("hr_view_employee", employee_id=employee_id))

    contracts = EmployeeContract.query.filter_by(employee_id=employee_id).order_by(EmployeeContract.created_at.desc()).all()
    managers = Employee.query.filter(Employee.employee_id != employee_id, Employee.employee_status == "ACTIVE").all()
    hr_documents = EmployeeHRDocument.query.filter_by(employee_id=employee_id).all()

    return render_template(
        "hr_edit_employee_info.html",
        employee=employee,
        contracts=contracts,
        managers=managers,
        hr_documents=hr_documents,
    )


# ── Bulk Excel Export with Filters ───────────────────────────────────────────

@app.route("/hr/employees")
@login_required
@role_required("HR", "ADMIN")
def hr_employees_list():
    status_filter = request.args.get("status", "active")  # active | left | all
    search_query = request.args.get("q", "").strip()

    query = Employee.query

    # Apply status filter
    if status_filter == "active":
        query = query.filter(Employee.employee_status == "ACTIVE")
    elif status_filter == "left":
        query = query.filter(Employee.employee_status == "LEFT")
    # "all" shows both

    # Apply search filter
    if search_query:
        query = query.filter(
            (Employee.first_name.ilike(f"%{search_query}%")) |
            (Employee.last_name.ilike(f"%{search_query}%"))  |
            (Employee.employee_code.ilike(f"%{search_query}%")) |
            (Employee.department.ilike(f"%{search_query}%"))  |
            (Employee.designation.ilike(f"%{search_query}%"))
        )

    employees = query.order_by(Employee.employee_code).all()

    # Count statistics
    total_count = Employee.query.count()
    active_count = Employee.query.filter_by(employee_status="ACTIVE").count()
    left_count = Employee.query.filter_by(employee_status="LEFT").count()

    return render_template(
        "hr_employees_list.html",
        employees=employees,
        status_filter=status_filter,
        search_query=search_query,
        total_count=total_count,
        active_count=active_count,
        left_count=left_count,
    )


@app.route("/hr/export-employees", methods=["GET", "POST"])
@login_required
@role_required("HR")
def hr_export_employees():
    from export_utils import EXPORT_COLUMNS, generate_employee_excel, get_all_field_keys

    if request.method == "POST":
        # Get selected fields
        selected_fields = request.form.getlist("fields")

        if not selected_fields:
            flash("Please select at least one field to export.", "warning")
            return redirect(url_for("hr_export_employees"))

        # Build query with filters
        query = Employee.query
        filters_applied = {}

        # Filter by status
        status_filter = request.form.get("status_filter")
        if status_filter:
            query = query.filter(Employee.employee_status == status_filter)
            filters_applied['Status'] = status_filter

        # Filter by department
        department_filter = request.form.get("department_filter")
        if department_filter:
            query = query.filter(Employee.department.ilike(f"%{department_filter}%"))
            filters_applied['Department'] = department_filter

        # Filter by designation
        designation_filter = request.form.get("designation_filter")
        if designation_filter:
            query = query.filter(Employee.designation.ilike(f"%{designation_filter}%"))
            filters_applied['Designation'] = designation_filter

        # Filter by employment type
        employment_type_filter = request.form.get("employment_type_filter")
        if employment_type_filter:
            query = query.filter(Employee.employment_type == employment_type_filter)
            filters_applied['Employment Type'] = employment_type_filter

        # Filter by date range
        joining_from = request.form.get("joining_from")
        joining_to = request.form.get("joining_to")
        if joining_from:
            query = query.filter(Employee.joining_date >= datetime.strptime(joining_from, "%Y-%m-%d").date())
            filters_applied['Joined From'] = joining_from
        if joining_to:
            query = query.filter(Employee.joining_date <= datetime.strptime(joining_to, "%Y-%m-%d").date())
            filters_applied['Joined To'] = joining_to

        # Execute query
        employees = query.order_by(Employee.employee_code).all()

        if not employees:
            flash("No employees found matching the selected filters.", "info")
            return redirect(url_for("hr_export_employees"))

        # Generate Excel file
        excel_file = generate_employee_excel(employees, selected_fields, filters_applied)

        # Log the export action
        log_action(current_user.user_id, "EXPORT_EMPLOYEES", "employees", None,
                   f"Exported {len(employees)} employee records")

        # Send file as download
        from flask import send_file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"employee_export_{timestamp}.xlsx"

        return send_file(
            excel_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )

    # GET request - show export form
    # Get unique departments and designations for filters
    departments = db.session.query(Employee.department).filter(
        Employee.department.isnot(None), Employee.department != ""
    ).distinct().order_by(Employee.department).all()
    departments = [d[0] for d in departments]

    designations = db.session.query(Employee.designation).filter(
        Employee.designation.isnot(None), Employee.designation != ""
    ).distinct().order_by(Employee.designation).all()
    designations = [d[0] for d in designations]

    return render_template(
        "hr_export_employees.html",
        export_columns=EXPORT_COLUMNS,
        departments=departments,
        designations=designations,
    )
