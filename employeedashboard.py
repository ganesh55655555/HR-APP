import json
import os
from datetime import datetime

from flask import (
    render_template, request, redirect, url_for,
    flash, send_from_directory, abort, current_app
)
from flask_login import login_required, current_user

from app import app
from sql import db, Employee, EmployeeProfile, EmployeePayslip, \
    EmployeeHRDocument, ProfileEditRequest, EmployeeFamily, EmployeeAsset, EmployeeContract
from utils import role_required, save_upload

TOTAL_STEPS = 6

EDITABLE_FIELDS = [
    ("personal_email",  "Personal Email"),
    ("mobile_number",   "Mobile Number"),
    ("whatsapp_number", "WhatsApp Number"),
    ("marital_status",  "Marital Status"),
    ("perm_address_line1", "Permanent Address Line 1"),
    ("perm_address_line2", "Permanent Address Line 2"),
    ("perm_city",       "Permanent City"),
    ("perm_state",      "Permanent State"),
    ("perm_country",    "Permanent Country"),
    ("perm_postal_code","Permanent Postal Code"),
    ("curr_address_line1", "Current Address Line 1"),
    ("curr_address_line2", "Current Address Line 2"),
    ("curr_city",       "Current City"),
    ("curr_state",      "Current State"),
    ("curr_country",    "Current Country"),
    ("curr_postal_code","Current Postal Code"),
    ("bank_name",       "Bank Name"),
    ("account_number",  "Account Number"),
    ("branch_name",     "Branch Name"),
    ("ifsc_code",       "IFSC Code"),
    ("pf_number",       "PF Number"),
    ("uan_number",      "UAN Number"),
    ("esi_number",      "ESI Number"),
]


def _get_or_404_profile():
    profile = EmployeeProfile.query.filter_by(user_id=current_user.user_id).first()
    if not profile:
        abort(404)
    return profile


# ─── Multi-step Registration ───────────────────────────────────────────────────

@app.route("/profile/step/<int:step>", methods=["GET", "POST"])
@login_required
@role_required("EMPLOYEE")
def profile_step(step):
    if step < 1 or step > TOTAL_STEPS:
        abort(404)

    profile = EmployeeProfile.query.filter_by(user_id=current_user.user_id).first()
    if not profile:
        profile = EmployeeProfile(user_id=current_user.user_id, status="DRAFT")
        db.session.add(profile)
        db.session.commit()

    if profile.status == "APPROVED":
        flash("Your profile is approved. Use 'Edit My Info' to request changes.", "info")
        return redirect(url_for("employee_info"))

    if request.method == "POST":
        try:
            _save_step(step, profile)
            db.session.commit()
            action = request.form.get("action", "next")
            if action == "next" and step < TOTAL_STEPS:
                return redirect(url_for("profile_step", step=step + 1))
            elif action == "prev" and step > 1:
                return redirect(url_for("profile_step", step=step - 1))
            else:
                return redirect(url_for("profile_review"))
        except ValueError as e:
            # Flash message already set in _save_step, just rollback and re-render
            db.session.rollback()
            return render_template(
                f"profile/step{step}.html",
                profile=profile, step=step, total_steps=TOTAL_STEPS,
            )

    return render_template(
        f"profile/step{step}.html",
        profile=profile, step=step, total_steps=TOTAL_STEPS,
    )


def _save_step(step, profile):
    f = request.form
    if step == 1:
        profile.first_name    = f.get("first_name", "").strip()
        profile.middle_name   = f.get("middle_name", "").strip()
        profile.last_name     = f.get("last_name", "").strip()
        dob = f.get("date_of_birth")
        profile.date_of_birth = datetime.strptime(dob, "%Y-%m-%d").date() if dob else None
        profile.gender        = f.get("gender")
        profile.blood_group   = f.get("blood_group")
        profile.religion      = f.get("religion")
        profile.nationality   = f.get("nationality")
        profile.place_of_birth = f.get("place_of_birth")
        profile.mother_tongue = f.get("mother_tongue")
        profile.marital_status = f.get("marital_status")
        profile.personal_email = f.get("personal_email")

        # Validate mobile number (10 digits)
        mobile = f.get("mobile_number", "").strip()
        if not mobile or not mobile.isdigit() or len(mobile) != 10:
            flash("Mobile number must be exactly 10 digits.", "danger")
            raise ValueError("Invalid mobile number")
        profile.mobile_number = mobile

        # Validate WhatsApp number (10 digits)
        whatsapp = f.get("whatsapp_number", "").strip()
        if not whatsapp or not whatsapp.isdigit() or len(whatsapp) != 10:
            flash("WhatsApp number must be exactly 10 digits.", "danger")
            raise ValueError("Invalid WhatsApp number")
        profile.whatsapp_number = whatsapp

        # Family Information (now in Step 1)
        mother_name = f.get("family_mother_name", "").strip()
        father_name = f.get("family_father_name", "").strip()
        spouse_name = f.get("family_spouse_name", "").strip()

        if not mother_name or not father_name:
            flash("Mother's name and Father's name are mandatory.", "danger")
            raise ValueError("Family names required")

        # Validate spouse name if married
        if profile.marital_status == "Married" and not spouse_name:
            flash("Spouse name is required for married employees.", "danger")
            raise ValueError("Spouse name required for married status")

        family_info = {
            "mother_name": mother_name,
            "father_name": father_name,
            "spouse_name": spouse_name,
            "epf_member": f.get("family_epf_member") == "yes",
            "family_pension_scheme": f.get("family_pension_scheme", ""),
        }
        profile.family_info_json = json.dumps(family_info)

        # Languages Known
        languages = f.get("languages_known", "").strip()
        if not languages:
            flash("Languages known is mandatory.", "danger")
            raise ValueError("Languages required")
        profile.languages_known = languages

        # References (all 3 mandatory)
        profile.ref1_name = f.get("ref1_name", "").strip()
        profile.ref1_email = f.get("ref1_email", "").strip()
        profile.ref1_phone = f.get("ref1_phone", "").strip()
        profile.ref1_relationship = f.get("ref1_relationship", "").strip()

        profile.ref2_name = f.get("ref2_name", "").strip()
        profile.ref2_email = f.get("ref2_email", "").strip()
        profile.ref2_phone = f.get("ref2_phone", "").strip()
        profile.ref2_relationship = f.get("ref2_relationship", "").strip()

        profile.ref3_name = f.get("ref3_name", "").strip()
        profile.ref3_email = f.get("ref3_email", "").strip()
        profile.ref3_phone = f.get("ref3_phone", "").strip()
        profile.ref3_relationship = f.get("ref3_relationship", "").strip()

        # Validate all reference fields are filled
        if not all([profile.ref1_name, profile.ref1_email, profile.ref1_phone, profile.ref1_relationship]):
            flash("Reference 1: All fields are mandatory.", "danger")
            raise ValueError("Reference 1 incomplete")
        if not all([profile.ref2_name, profile.ref2_email, profile.ref2_phone, profile.ref2_relationship]):
            flash("Reference 2: All fields are mandatory.", "danger")
            raise ValueError("Reference 2 incomplete")
        if not all([profile.ref3_name, profile.ref3_email, profile.ref3_phone, profile.ref3_relationship]):
            flash("Reference 3: All fields are mandatory.", "danger")
            raise ValueError("Reference 3 incomplete")

        # Validate phone numbers (10 digits)
        for i, phone in enumerate([profile.ref1_phone, profile.ref2_phone, profile.ref3_phone], 1):
            if not phone.isdigit() or len(phone) != 10:
                flash(f"Reference {i}: Phone number must be exactly 10 digits.", "danger")
                raise ValueError(f"Invalid reference {i} phone")

        photo = request.files.get("photo")
        if photo and photo.filename:
            path = save_upload(photo, "photos")
            if path:
                profile.photo_path = path

        # Photo is mandatory for new profiles
        if not profile.photo_path:
            flash("Profile photo is mandatory.", "danger")
            raise ValueError("Photo required")

        profile.step1_done = True

    elif step == 2:
        profile.perm_address_line1 = f.get("perm_address_line1")
        profile.perm_address_line2 = f.get("perm_address_line2")
        profile.perm_city          = f.get("perm_city")
        profile.perm_state         = f.get("perm_state")
        profile.perm_country       = f.get("perm_country")
        profile.perm_postal_code   = f.get("perm_postal_code")
        profile.curr_same_as_perm  = "curr_same_as_perm" in f
        if profile.curr_same_as_perm:
            profile.curr_address_line1 = profile.perm_address_line1
            profile.curr_address_line2 = profile.perm_address_line2
            profile.curr_city          = profile.perm_city
            profile.curr_state         = profile.perm_state
            profile.curr_country       = profile.perm_country
            profile.curr_postal_code   = profile.perm_postal_code
        else:
            profile.curr_address_line1 = f.get("curr_address_line1")
            profile.curr_address_line2 = f.get("curr_address_line2")
            profile.curr_city          = f.get("curr_city")
            profile.curr_state         = f.get("curr_state")
            profile.curr_country       = f.get("curr_country")
            profile.curr_postal_code   = f.get("curr_postal_code")
        profile.step2_done = True

    elif step == 3:
        names  = f.getlist("ec_name")
        rels   = f.getlist("ec_relationship")
        phones = f.getlist("ec_phone")

        # Get personal mobile number from profile
        personal_mobile = (profile.mobile_number or "").strip()

        # Collect valid contacts
        contacts = []
        seen_phones = set()

        for n, r, p in zip(names, rels, phones):
            n_stripped = n.strip()
            r_stripped = r.strip()
            p_stripped = p.strip()

            if not n_stripped or not r_stripped or not p_stripped:
                flash("All fields (name, relationship, phone) are required for each emergency contact.", "danger")
                raise ValueError("Missing required emergency contact fields")

            # Validate phone number format (10 digits)
            if not p_stripped.isdigit() or len(p_stripped) != 10:
                flash(f"Phone number '{p_stripped}' must be exactly 10 digits.", "danger")
                raise ValueError("Invalid phone number format")

            # Check if phone matches personal mobile (only if personal mobile exists)
            if personal_mobile and p_stripped == personal_mobile:
                flash(f"Emergency contact phone number '{p_stripped}' cannot be the same as your personal mobile number '{personal_mobile}'.", "danger")
                raise ValueError("Emergency contact matches personal number")

            # Check for duplicate phone numbers
            if p_stripped in seen_phones:
                flash("Duplicate emergency contact phone numbers detected. All phone numbers must be unique.", "danger")
                raise ValueError("Duplicate emergency contact phone")

            seen_phones.add(p_stripped)
            contacts.append({"name": n_stripped, "relationship": r_stripped, "phone": p_stripped})

        # Must have exactly 2 emergency contacts
        if len(contacts) != 2:
            flash("You must provide exactly 2 emergency contacts.", "danger")
            raise ValueError("Must have 2 emergency contacts")

        profile.emergency_contacts_json = json.dumps(contacts)
        profile.step3_done = True

    elif step == 4:
        profile.designation = f.get("designation")
        profile.department  = f.get("department")
        jd = f.get("joining_date")
        profile.joining_date = datetime.strptime(jd, "%Y-%m-%d").date() if jd else None

        # Previous employment history - mandatory
        employers  = f.getlist("employer_name")
        positions  = f.getlist("position_held")
        from_dates = f.getlist("emp_from")
        to_dates   = f.getlist("emp_to")

        history = []
        for e, p, fr, to in zip(employers, positions, from_dates, to_dates):
            e_stripped = e.strip()
            p_stripped = p.strip()

            # Skip if both employer and position are empty
            if not e_stripped and not p_stripped:
                continue

            # If one is filled, both must be filled
            if not e_stripped or not p_stripped:
                flash("Employer name and position are required for each employment record.", "danger")
                raise ValueError("Incomplete employment record")

            history.append({
                "employer": e_stripped,
                "position": p_stripped,
                "from": fr if fr else "",
                "to": to if to else ""
            })

        # Must have at least 1 employment history record
        if len(history) < 1:
            flash("You must provide at least one previous employment record.", "danger")
            raise ValueError("No employment history")

        profile.employment_history_json = json.dumps(history)
        profile.step4_done = True

    elif step == 5:
        profile.bank_name      = f.get("bank_name")
        profile.account_number = f.get("account_number")
        profile.branch_name    = f.get("branch_name")
        profile.ifsc_code      = f.get("ifsc_code")
        profile.pf_number      = f.get("pf_number")
        profile.uan_number     = f.get("uan_number")
        profile.esi_number     = f.get("esi_number", "").strip()
        if not profile.esi_number:
            flash("ESI number is mandatory.", "danger")
            raise ValueError("ESI number required")
        profile.step5_done = True

    elif step == 6:
        doc_types   = f.getlist("doc_type")
        doc_numbers = f.getlist("doc_number")
        doc_files   = request.files.getlist("doc_file")
        existing    = json.loads(profile.documents_json or "[]")
        existing_map = {d["type"]: d for d in existing}

        # Mandatory documents
        mandatory_docs = ["Aadhar Card", "PAN Card", "10th Certificate", "12th Certificate", "Degree Certificate"]

        docs = []
        for dtype, dnum, dfile in zip(doc_types, doc_numbers, doc_files):
            if not dtype:
                continue

            # Validate document number
            if dtype in mandatory_docs:
                if not dnum or not dnum.strip():
                    flash(f"{dtype} number is required.", "danger")
                    raise ValueError(f"Missing {dtype} number")

                # Validate Aadhar number (12 digits)
                if dtype == "Aadhar Card":
                    if not dnum.isdigit() or len(dnum) != 12:
                        flash("Aadhar number must be exactly 12 digits.", "danger")
                        raise ValueError("Invalid Aadhar number")

                # Validate PAN number format
                if dtype == "PAN Card":
                    dnum_upper = dnum.upper()
                    if len(dnum_upper) != 10 or not dnum_upper[:5].isalpha() or not dnum_upper[5:9].isdigit() or not dnum_upper[9].isalpha():
                        flash("PAN number must be in format: XXXXX9999X (5 letters, 4 digits, 1 letter).", "danger")
                        raise ValueError("Invalid PAN format")
                    dnum = dnum_upper

            # Handle file upload
            path = None
            if dfile and dfile.filename:
                path = save_upload(dfile, "documents")
            if path is None:
                path = existing_map.get(dtype, {}).get("file_path")

            # For mandatory documents, file must be present
            if dtype in mandatory_docs and not path:
                flash(f"{dtype} file upload is required.", "danger")
                raise ValueError(f"Missing {dtype} file")

            docs.append({"type": dtype, "number": dnum, "file_path": path})

        # Verify all mandatory documents are present
        uploaded_types = {d["type"] for d in docs}
        missing_docs = set(mandatory_docs) - uploaded_types
        if missing_docs:
            flash(f"Missing mandatory documents: {', '.join(missing_docs)}", "danger")
            raise ValueError("Missing mandatory documents")

        profile.documents_json = json.dumps(docs)
        profile.step6_done = True


@app.route("/profile/review", methods=["GET", "POST"])
@login_required
@role_required("EMPLOYEE")
def profile_review():
    profile = _get_or_404_profile()
    if request.method == "POST":
        if profile.status == "APPROVED":
            flash("Already approved.", "info")
            return redirect(url_for("employee_dashboard"))
        profile.status       = "PENDING"
        profile.submitted    = True
        profile.submitted_at = datetime.utcnow()
        db.session.commit()
        flash("Profile submitted for HR review!", "success")
        return redirect(url_for("employee_dashboard"))

    ec      = json.loads(profile.emergency_contacts_json or "[]")
    history = json.loads(profile.employment_history_json or "[]")
    docs    = json.loads(profile.documents_json or "[]")
    return render_template(
        "profile/review.html",
        profile=profile, emergency_contacts=ec,
        employment_history=history, documents=docs,
        total_steps=TOTAL_STEPS,
    )


# ─── Employee Dashboard (landing) ─────────────────────────────────────────────

@app.route("/employee/dashboard")
@login_required
@role_required("EMPLOYEE")
def employee_dashboard():
    profile  = EmployeeProfile.query.filter_by(user_id=current_user.user_id).first()
    employee = Employee.query.filter_by(user_id=current_user.user_id).first()
    return render_template(
        "employee_dashboard.html",
        profile=profile, employee=employee,
    )


# ─── Tab 1: My Information (editable, approval flow) ──────────────────────────

@app.route("/employee/info")
@login_required
@role_required("EMPLOYEE")
def employee_info():
    employee = Employee.query.filter_by(user_id=current_user.user_id).first()
    profile  = EmployeeProfile.query.filter_by(user_id=current_user.user_id).first()

    if not employee:
        # Not approved yet — send to profile wizard
        return redirect(url_for("profile_step", step=1))

    ec = json.loads(employee.emergency_contacts_json or "[]")
    pending_req = ProfileEditRequest.query.filter_by(
        employee_id=employee.employee_id, status="PENDING"
    ).first()

    return render_template(
        "employee_info.html",
        employee=employee, profile=profile,
        emergency_contacts=ec,
        pending_req=pending_req,
        editable_fields=EDITABLE_FIELDS,
    )


@app.route("/employee/info/edit-all", methods=["GET", "POST"])
@login_required
@role_required("EMPLOYEE")
def employee_edit_all_info():
    """Employee can edit personal, family, and asset information"""
    employee = Employee.query.filter_by(user_id=current_user.user_id).first()
    if not employee:
        abort(403)

    if request.method == "POST":
        f = request.form

        # Update Personal Information
        employee.first_name = f.get("first_name", "").strip()
        employee.middle_name = f.get("middle_name", "").strip()
        employee.last_name = f.get("last_name", "").strip()

        dob = f.get("date_of_birth")
        if dob:
            from datetime import datetime
            employee.date_of_birth = datetime.strptime(dob, "%Y-%m-%d").date()

        employee.gender = f.get("gender")
        employee.blood_group = f.get("blood_group")
        employee.nationality = f.get("nationality", "").strip()
        employee.religion = f.get("religion", "").strip()
        employee.mother_tongue = f.get("mother_tongue", "").strip()
        employee.marital_status = f.get("marital_status")
        employee.mobile_number = f.get("mobile_number", "").strip()
        employee.whatsapp_number = f.get("whatsapp_number", "").strip()
        employee.personal_email = f.get("personal_email", "").strip()
        employee.languages_known = f.get("languages_known", "").strip()

        # Update Address Information
        employee.perm_address_line1 = f.get("perm_address_line1", "").strip()
        employee.perm_address_line2 = f.get("perm_address_line2", "").strip()
        employee.perm_city = f.get("perm_city", "").strip()
        employee.perm_state = f.get("perm_state", "").strip()
        employee.perm_country = f.get("perm_country", "").strip()
        employee.perm_postal_code = f.get("perm_postal_code", "").strip()

        employee.curr_address_line1 = f.get("curr_address_line1", "").strip()
        employee.curr_address_line2 = f.get("curr_address_line2", "").strip()
        employee.curr_city = f.get("curr_city", "").strip()
        employee.curr_state = f.get("curr_state", "").strip()
        employee.curr_country = f.get("curr_country", "").strip()
        employee.curr_postal_code = f.get("curr_postal_code", "").strip()

        # Update Bank Information
        employee.bank_name = f.get("bank_name", "").strip()
        employee.account_number = f.get("account_number", "").strip()
        employee.branch_name = f.get("branch_name", "").strip()
        employee.ifsc_code = f.get("ifsc_code", "").strip()
        employee.uan_number = f.get("uan_number", "").strip()
        employee.esi_number = f.get("esi_number", "").strip()

        # Update Family Information
        family = EmployeeFamily.query.filter_by(employee_id=employee.employee_id).first()
        if not family:
            family = EmployeeFamily(employee_id=employee.employee_id)
            db.session.add(family)

        family.mother_name = f.get("family_mother_name", "").strip()
        family.father_name = f.get("family_father_name", "").strip()
        family.spouse_name = f.get("family_spouse_name", "").strip()
        family.epf_member = f.get("family_epf_member") == "yes"
        family.family_pension_scheme = f.get("family_pension_scheme", "").strip()

        if not family.mother_name or not family.father_name:
            flash("Mother's name and Father's name are mandatory.", "danger")
            return redirect(request.url)

        db.session.commit()
        log_action(current_user.user_id, "EMPLOYEE_EDIT_INFO", "employees", employee.employee_id,
                   f"Updated personal and family info")
        flash("Your information updated successfully.", "success")
        return redirect(url_for("employee_info"))

    family = EmployeeFamily.query.filter_by(employee_id=employee.employee_id).first()

    return render_template(
        "employee_edit_all_info.html",
        employee=employee,
        family=family,
    )


@app.route("/employee/info/edit-family-asset", methods=["GET", "POST"])
@login_required
@role_required("EMPLOYEE")
def employee_edit_family_asset():
    """Employee can edit their own family and asset information"""
    employee = Employee.query.filter_by(user_id=current_user.user_id).first()
    if not employee:
        abort(403)

    if request.method == "POST":
        f = request.form

        # Update Family Information
        family = EmployeeFamily.query.filter_by(employee_id=employee.employee_id).first()
        if not family:
            family = EmployeeFamily(employee_id=employee.employee_id)
            db.session.add(family)

        family.mother_name = f.get("family_mother_name", "").strip()
        family.father_name = f.get("family_father_name", "").strip()
        family.spouse_name = f.get("family_spouse_name", "").strip()
        family.epf_member = f.get("family_epf_member") == "yes"
        family.family_pension_scheme = f.get("family_pension_scheme", "").strip()

        if not family.mother_name or not family.father_name:
            flash("Mother's name and Father's name are mandatory.", "danger")
            return redirect(request.url)

        # Update Asset Information
        asset = EmployeeAsset.query.filter_by(employee_id=employee.employee_id).first()
        if not asset:
            asset = EmployeeAsset(employee_id=employee.employee_id)
            db.session.add(asset)

        asset.access_office_field_1 = f.get("access_office_field_1", "").strip()
        asset.access_office_field_2 = f.get("access_office_field_2", "").strip()
        asset.access_office_field_3 = f.get("access_office_field_3", "").strip()
        asset.phone_number = f.get("asset_phone_number", "").strip()
        asset.bike_access_card_number = f.get("bike_access_card_number", "").strip()

        if not all([asset.access_office_field_1, asset.access_office_field_2,
                    asset.access_office_field_3, asset.phone_number, asset.bike_access_card_number]):
            flash("All asset fields are mandatory.", "danger")
            return redirect(request.url)

        db.session.commit()
        log_action(current_user.user_id, "EMPLOYEE_EDIT_FAMILY_ASSET", "employee_family", employee.employee_id,
                   f"Updated family and asset info")
        flash("Family and asset information updated successfully.", "success")
        return redirect(url_for("employee_info"))

    family = EmployeeFamily.query.filter_by(employee_id=employee.employee_id).first()
    asset = EmployeeAsset.query.filter_by(employee_id=employee.employee_id).first()

    return render_template(
        "employee_edit_family_asset.html",
        employee=employee,
        family=family,
        asset=asset,
    )


@app.route("/employee/info/edit", methods=["GET", "POST"])
@login_required
@role_required("EMPLOYEE")
def employee_edit_info():
    employee = Employee.query.filter_by(user_id=current_user.user_id).first()
    if not employee:
        abort(403)

    # Block if a pending request already exists
    pending = ProfileEditRequest.query.filter_by(
        employee_id=employee.employee_id, status="PENDING"
    ).first()
    if pending:
        flash("You already have a pending change request. Wait for HR to review it.", "warning")
        return redirect(url_for("employee_info"))

    if request.method == "POST":
        f = request.form
        changes = {}
        for field, _ in EDITABLE_FIELDS:
            val = f.get(field, "").strip()
            current_val = str(getattr(employee, field) or "")
            if val != current_val:
                changes[field] = val

        if not changes:
            flash("No changes detected.", "info")
            return redirect(url_for("employee_info"))

        reason = f.get("reason", "").strip()
        req = ProfileEditRequest(
            employee_id=employee.employee_id,
            changes_json=json.dumps(changes),
            reason=reason,
        )
        db.session.add(req)
        db.session.commit()
        flash("Change request submitted for HR approval.", "success")
        return redirect(url_for("employee_info"))

    # Pre-build a plain dict of current values so the template
    # doesn't need getattr (which Jinja2 doesn't expose)
    field_values = {field: (getattr(employee, field) or "") for field, _ in EDITABLE_FIELDS}

    return render_template(
        "employee_edit_info.html",
        employee=employee,
        field_values=field_values,
        editable_fields=EDITABLE_FIELDS,
    )


# ─── Tab 2: My Documents ──────────────────────────────────────────────────────

@app.route("/employee/documents")
@login_required
@role_required("EMPLOYEE")
def employee_documents():
    employee = Employee.query.filter_by(user_id=current_user.user_id).first()
    if not employee:
        flash("Your profile is not approved yet.", "warning")
        return redirect(url_for("employee_dashboard"))

    # Last 3 payslips only
    payslips = (
        EmployeePayslip.query
        .filter_by(employee_id=employee.employee_id)
        .order_by(EmployeePayslip.year.desc(), EmployeePayslip.month.desc())
        .limit(3).all()
    )

    hr_docs = (
        EmployeeHRDocument.query
        .filter_by(employee_id=employee.employee_id)
        .order_by(EmployeeHRDocument.uploaded_at.desc())
        .all()
    )

    # Group HR docs by type
    from collections import defaultdict
    docs_by_type = defaultdict(list)
    for d in hr_docs:
        docs_by_type[d.doc_type].append(d)

    month_names = ["","January","February","March","April","May","June",
                   "July","August","September","October","November","December"]

    return render_template(
        "employee_documents.html",
        employee=employee,
        payslips=payslips,
        docs_by_type=dict(docs_by_type),
        month_names=month_names,
    )


# ─── Payslip download (employee, last 3 only) ─────────────────────────────────

@app.route("/employee/payslip/download/<int:payslip_id>")
@login_required
@role_required("EMPLOYEE")
def download_payslip(payslip_id):
    employee = Employee.query.filter_by(user_id=current_user.user_id).first()
    if not employee:
        abort(403)
    payslip = EmployeePayslip.query.filter_by(
        payslip_id=payslip_id, employee_id=employee.employee_id,
    ).first_or_404()
    allowed_ids = [
        p.payslip_id for p in
        EmployeePayslip.query
        .filter_by(employee_id=employee.employee_id)
        .order_by(EmployeePayslip.year.desc(), EmployeePayslip.month.desc())
        .limit(3).all()
    ]
    if payslip_id not in allowed_ids:
        abort(403)
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    full_path = os.path.join(upload_folder, payslip.file_path)
    return send_from_directory(
        os.path.dirname(full_path), os.path.basename(full_path), as_attachment=True
    )
