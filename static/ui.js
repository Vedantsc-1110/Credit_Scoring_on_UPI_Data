(function () {
    const config = window.__MASTERMIND_UI__;
    if (!config) {
        return;
    }

    const page = document.body.dataset.page || "";
    const initialHealth = window.__MASTERMIND_HEALTH_SNAPSHOT__ || null;
    const state = {
        tier: "REDUCED",
    };
    const THEME_STORAGE_KEY = "mastermind-theme";

    const FIELD_GROUPS = {
        application: [
            "AMT_INCOME_TOTAL_CAPPED",
            "AMT_CREDIT",
            "AMT_ANNUITY",
            "AMT_GOODS_PRICE",
            "DAYS_BIRTH",
            "DAYS_EMPLOYED",
            "DAYS_REGISTRATION",
            "DAYS_ID_PUBLISH",
            "DAYS_LAST_PHONE_CHANGE",
            "EXT_SOURCE_1",
            "EXT_SOURCE_2",
            "EXT_SOURCE_3",
            "NAME_CONTRACT_TYPE",
            "NAME_EDUCATION_TYPE",
            "NAME_FAMILY_STATUS",
            "OCCUPATION_TYPE",
            "ORGANIZATION_TYPE",
        ],
        bureau_agg: [
            "BUREAU_LOAN_COUNT",
            "BUREAU_ACTIVE_COUNT",
            "BUREAU_CLOSED_COUNT",
            "BUREAU_AMT_CREDIT_SUM_SUM",
            "BUREAU_AMT_CREDIT_SUM_DEBT_SUM",
            "BUREAU_DEBT_TO_CREDIT_RATIO",
            "BUREAU_AMT_CREDIT_SUM_OVERDUE_SUM",
            "BUREAU_CREDIT_DAY_OVERDUE_MAX",
            "BUREAU_DAYS_CREDIT_MAX",
            "BUREAU_CNT_CREDIT_PROLONG_SUM",
        ],
        previous_agg: [
            "PREV_APP_COUNT",
            "PREV_APPROVED_COUNT",
            "PREV_REFUSED_COUNT",
            "PREV_APPROVAL_RATE",
            "PREV_REFUSAL_RATE",
            "PREV_AMT_APPLICATION_MEAN",
            "PREV_AMT_CREDIT_MEAN",
            "PREV_AMT_GOODS_PRICE_MEAN",
            "PREV_APP_CREDIT_DIFF_MEAN",
            "PREV_DAYS_DECISION_MAX",
            "PREV_RATE_DOWN_PAYMENT_MEAN",
        ],
        installments_agg: [
            "INST_RECORD_COUNT",
            "INST_MISSED_RATE",
            "INST_DPD_MEAN",
            "INST_DPD_MAX",
            "INST_PAYMENT_RATIO_MEAN",
            "INST_PAYMENT_RATIO_MIN",
            "INST_LATE_COUNT",
        ],
        pos_cash_agg: [
            "POS_RECORD_COUNT",
            "POS_DPD_MEAN",
            "POS_DPD_MAX",
            "POS_DPD_DEF_MEAN",
            "POS_DPD_DEF_MAX",
            "POS_COMPLETED_RATE",
            "POS_ACTIVE_RATE",
            "POS_CNT_INSTALMENT_FUTURE_MEAN",
        ],
        credit_card_agg: [
            "CC_RECORD_COUNT",
            "CC_BALANCE_MEAN",
            "CC_LIMIT_MEAN",
            "CC_UTILIZATION_MEAN",
            "CC_PAYMENT_RATIO_MEAN",
            "CC_DPD_MEAN",
            "CC_DPD_MAX",
            "CC_DRAWINGS_ATM_SUM",
            "CC_DRAWINGS_CURRENT_SUM",
        ],
        upi_agg: [
            "monthly_inflow",
            "monthly_outflow",
            "monthly_txn_count",
            "avg_txn_value",
            "median_txn_value",
            "inflow_txn_count",
            "outflow_txn_count",
            "weekday_txn_ratio",
            "weekend_txn_ratio",
            "distinct_counterparties",
            "active_days",
        ],
    };

    const DERIVED_FIELDS = {
        application: new Set(["DAYS_EMPLOYED_ANOM"]),
        bureau_agg: new Set(["BUREAU_DEBT_TO_CREDIT_RATIO"]),
        previous_agg: new Set(["PREV_APPROVAL_RATE", "PREV_REFUSAL_RATE", "PREV_APP_CREDIT_DIFF_MEAN", "PREV_RATE_DOWN_PAYMENT_MEAN"]),
        installments_agg: new Set(["INST_MISSED_RATE", "INST_PAYMENT_RATIO_MEAN", "INST_PAYMENT_RATIO_MIN"]),
        pos_cash_agg: new Set(["POS_COMPLETED_RATE", "POS_ACTIVE_RATE"]),
        credit_card_agg: new Set(["CC_UTILIZATION_MEAN", "CC_PAYMENT_RATIO_MEAN"]),
        upi_agg: new Set([
            "balance_instability_score",
            "failed_due_to_low_balance",
            "failed_txn_count",
            "outflow_volatility",
            "inflow_volatility",
            "txn_value_std",
            "success_txn_count",
            "peak_txn_day_count",
        ]),
    };

    const FIELD_COPY = {
        AMT_INCOME_TOTAL_CAPPED: ["Monthly/Annual Income", "Enter the applicant's total income used for credit assessment."],
        AMT_CREDIT: ["Loan Amount Requested", "Total credit amount requested by the applicant."],
        AMT_ANNUITY: ["Expected EMI / Annuity", "Regular repayment amount for the loan."],
        AMT_GOODS_PRICE: ["Goods Price", "Price of the item or asset being financed."],
        DAYS_BIRTH: ["Age In Days", "Enter age converted to days, as a positive number. Example: 35 years is about 12784 days."],
        DAYS_EMPLOYED: ["Employment Length In Days", "Enter total days employed as a positive number. The system handles special anomaly flags."],
        DAYS_REGISTRATION: ["Days Since Registration", "How long ago the applicant changed registration details. Enter a positive number of days."],
        DAYS_ID_PUBLISH: ["Days Since ID Was Issued", "How long ago the applicant's ID document was issued. Enter a positive number of days."],
        DAYS_LAST_PHONE_CHANGE: ["Days Since Phone Changed", "How long ago the applicant changed phone number. Enter a positive number of days."],
        EXT_SOURCE_1: ["External Credit Score 1", "Score between 0 and 1 from an external source."],
        EXT_SOURCE_2: ["External Credit Score 2", "Score between 0 and 1 from an external source."],
        EXT_SOURCE_3: ["External Credit Score 3", "Score between 0 and 1 from an external source."],
        NAME_CONTRACT_TYPE: ["Loan Type", "Choose the contract type."],
        NAME_EDUCATION_TYPE: ["Education Level", "Applicant's highest education level."],
        NAME_FAMILY_STATUS: ["Family Status", "Applicant's current family status."],
        OCCUPATION_TYPE: ["Occupation", "Applicant's occupation category."],
        ORGANIZATION_TYPE: ["Organization Type", "Applicant's employer or organization type."],
        BUREAU_LOAN_COUNT: ["Bureau Loan Count", "Number of credit bureau loans found for this applicant."],
        BUREAU_ACTIVE_COUNT: ["Active Bureau Loans", "Number of currently active bureau loans."],
        BUREAU_CLOSED_COUNT: ["Closed Bureau Loans", "Number of closed bureau loans."],
        BUREAU_AMT_CREDIT_SUM_SUM: ["Total Bureau Credit", "Total sanctioned credit amount across bureau loans."],
        BUREAU_AMT_CREDIT_SUM_DEBT_SUM: ["Total Bureau Debt", "Outstanding debt across bureau loans."],
        BUREAU_AMT_CREDIT_SUM_OVERDUE_SUM: ["Total Overdue Bureau Amount", "Total overdue amount reported by bureau."],
        BUREAU_CREDIT_DAY_OVERDUE_MAX: ["Max Bureau Days Overdue", "Maximum days overdue on bureau loans."],
        BUREAU_DAYS_CREDIT_MAX: ["Most Recent Bureau Credit Age", "Days since the most recent bureau credit record."],
        BUREAU_CNT_CREDIT_PROLONG_SUM: ["Credit Prolongations", "Total number of bureau credit prolongations."],
        PREV_APP_COUNT: ["Previous Application Count", "Number of previous applications."],
        PREV_APPROVED_COUNT: ["Previous Approved Count", "Number of previous applications approved."],
        PREV_REFUSED_COUNT: ["Previous Refused Count", "Number of previous applications refused."],
        PREV_AMT_APPLICATION_MEAN: ["Average Previous Requested Amount", "Average amount requested in previous applications."],
        PREV_AMT_CREDIT_MEAN: ["Average Previous Approved Credit", "Average credit amount granted previously."],
        PREV_AMT_GOODS_PRICE_MEAN: ["Average Previous Goods Price", "Average goods price in previous applications."],
        PREV_DAYS_DECISION_MAX: ["Most Recent Previous Decision Age", "Days since the most recent previous application decision."],
        PREV_RATE_DOWN_PAYMENT_MEAN: ["Average Down Payment Rate", "Average down payment ratio from previous applications."],
        INST_RECORD_COUNT: ["Installment Record Count", "Number of installment payment records."],
        INST_DPD_MEAN: ["Average Installment Days Past Due", "Average days past due across installment records."],
        INST_DPD_MAX: ["Max Installment Days Past Due", "Maximum days past due across installment records."],
        INST_PAYMENT_RATIO_MEAN: ["Average Installment Payment Ratio", "Average paid amount divided by expected installment amount."],
        INST_PAYMENT_RATIO_MIN: ["Minimum Installment Payment Ratio", "Lowest paid amount divided by expected installment amount."],
        INST_LATE_COUNT: ["Late Installment Count", "Number of late installment payments."],
        POS_RECORD_COUNT: ["POS Cash Record Count", "Number of POS cash records."],
        POS_DPD_MEAN: ["Average POS Days Past Due", "Average days past due for POS cash records."],
        POS_DPD_MAX: ["Max POS Days Past Due", "Maximum days past due for POS cash records."],
        POS_DPD_DEF_MEAN: ["Average POS Default DPD", "Average default-level days past due."],
        POS_DPD_DEF_MAX: ["Max POS Default DPD", "Maximum default-level days past due."],
        POS_CNT_INSTALMENT_FUTURE_MEAN: ["Average Future POS Installments", "Average remaining future installments."],
        CC_RECORD_COUNT: ["Credit Card Record Count", "Number of credit card records."],
        CC_BALANCE_MEAN: ["Average Credit Card Balance", "Average outstanding credit card balance."],
        CC_LIMIT_MEAN: ["Average Credit Card Limit", "Average credit card limit."],
        CC_PAYMENT_RATIO_MEAN: ["Average Credit Card Payment Ratio", "Average payment amount divided by due amount."],
        CC_DPD_MEAN: ["Average Credit Card Days Past Due", "Average credit card days past due."],
        CC_DPD_MAX: ["Max Credit Card Days Past Due", "Maximum credit card days past due."],
        CC_DRAWINGS_ATM_SUM: ["ATM Drawings Total", "Total ATM cash withdrawal amount on credit card."],
        CC_DRAWINGS_CURRENT_SUM: ["Current Drawings Total", "Total current drawing amount on credit card."],
        monthly_inflow: ["Monthly UPI Inflow", "Total money received through UPI in a month."],
        monthly_outflow: ["Monthly UPI Outflow", "Total money sent through UPI in a month."],
        monthly_txn_count: ["Monthly UPI Transaction Count", "Total UPI transactions in the month."],
        avg_txn_value: ["Average UPI Transaction Value", "Average amount per UPI transaction."],
        median_txn_value: ["Median UPI Transaction Value", "Middle transaction value for the month."],
        inflow_txn_count: ["UPI Inflow Transaction Count", "Number of incoming UPI transactions."],
        outflow_txn_count: ["UPI Outflow Transaction Count", "Number of outgoing UPI transactions."],
        weekday_txn_ratio: ["Weekday Transaction Ratio", "Share of UPI transactions on weekdays, from 0 to 1."],
        weekend_txn_ratio: ["Weekend Transaction Ratio", "Share of UPI transactions on weekends, from 0 to 1."],
        distinct_counterparties: ["Distinct UPI Counterparties", "Number of unique people or merchants transacted with."],
        active_days: ["Active UPI Days", "Number of days with at least one UPI transaction in the month."],
    };

    function cloneValue(value) {
        return JSON.parse(JSON.stringify(value || {}));
    }

    function navScrollState() {
        const nav = document.querySelector("[data-site-nav]");
        if (!nav) {
            return;
        }
        nav.classList.toggle("scrolled", window.scrollY > 60);
    }

    function setTheme(theme) {
        const nextTheme = theme === "dark" ? "dark" : "light";
        document.documentElement.dataset.theme = nextTheme;

        const toggle = document.querySelector("[data-theme-toggle]");
        const label = document.querySelector("[data-theme-toggle-text]");
        const isDark = nextTheme === "dark";

        if (toggle) {
            toggle.setAttribute("aria-pressed", isDark ? "true" : "false");
            toggle.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
        }
        if (label) {
            label.textContent = isDark ? "Light" : "Dark";
        }
    }

    function initThemeToggle() {
        let storedTheme = null;
        try {
            storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
        } catch (error) {
            storedTheme = null;
        }
        const preferredTheme = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
        setTheme(storedTheme || preferredTheme);

        const toggle = document.querySelector("[data-theme-toggle]");
        if (!toggle) {
            return;
        }

        toggle.addEventListener("click", function () {
            const currentTheme = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
            const nextTheme = currentTheme === "dark" ? "light" : "dark";
            try {
                window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
            } catch (error) {
                // Theme still changes for the current session when storage is unavailable.
            }
            setTheme(nextTheme);
        });
    }

    function formatCreditScore(probabilityValue, scoreValue) {
        const score = Number(scoreValue);
        if (Number.isFinite(score)) {
            return String(Math.round(Math.min(Math.max(score, 300), 900)));
        }
        const numeric = Number(probabilityValue);
        if (!Number.isFinite(numeric)) {
            return "-";
        }
        const probability = Math.min(Math.max(numeric, 0), 1);
        return String(Math.round(300 + ((1 - probability) * 600)));
    }

    function decisionClass(decision) {
        if (decision === "APPROVE") {
            return "approve";
        }
        if (decision === "DECLINE") {
            return "decline";
        }
        return "review";
    }

    async function readJson(response) {
        const text = await response.text();
        if (!text) {
            return {};
        }
        try {
            return JSON.parse(text);
        } catch (error) {
            return {
                error_code: "invalid_response",
                message: "The API returned invalid JSON.",
            };
        }
    }

    function clearValidation(form) {
        form.querySelectorAll(".invalid").forEach((field) => {
            field.classList.remove("invalid");
            field.removeAttribute("aria-invalid");
        });
    }

    function markInvalid(control) {
        control.classList.add("invalid");
        control.setAttribute("aria-invalid", "true");
    }

    function setTier(nextTier, elements) {
        state.tier = nextTier;
        elements.tierButtons.forEach((button) => {
            const active = button.dataset.tier === nextTier;
            button.classList.toggle("active", active);
            button.setAttribute("aria-selected", active ? "true" : "false");
        });

        const isFull = nextTier === "FULL";
        const isUpi = nextTier === "UPI";
        if (elements.applicationFields) {
            elements.applicationFields.classList.toggle("is-hidden", isUpi);
        }
        elements.bureauFields.classList.toggle("is-visible", isFull);
        elements.bureauDivider.classList.toggle("is-visible", isFull);
        if (elements.upiFields) {
            elements.upiFields.classList.toggle("is-visible", isUpi);
        }
        if (elements.upiDivider) {
            elements.upiDivider.classList.toggle("is-visible", isUpi);
        }
        elements.tierDescription.textContent = isFull
            ? "33 application fields + all 5 aggregate sections - full pipeline coverage"
            : isUpi
                ? "33 application fields + UPI transaction signals - standalone UPI model"
                : "33 fields - application section only";

        elements.resultSection.classList.add("is-hidden");
        elements.formStage.classList.remove("is-hidden");
        elements.loadingStage.classList.add("is-hidden");
        elements.feedback.textContent = "";
    }

    function valueFromControl(control) {
        const rawValue = control.value.trim();
        if (!rawValue) {
            return null;
        }

        if (control.dataset.type === "number") {
            const parsed = Number.parseFloat(rawValue);
            if (!Number.isFinite(parsed)) {
                return null;
            }
            if (control.dataset.negate === "true") {
                return -Math.abs(parsed);
            }
            return parsed;
        }

        return rawValue;
    }

    function sectionValue(payload, sectionName, fieldName) {
        const section = payload[sectionName] || {};
        const value = Number.parseFloat(section[fieldName]);
        return Number.isFinite(value) ? value : 0;
    }

    function setDerived(payload, sectionName, fieldName, value) {
        payload[sectionName] = payload[sectionName] || {};
        payload[sectionName][fieldName] = Number.isFinite(value) ? value : 0;
    }

    function ratio(numerator, denominator) {
        return denominator ? numerator / denominator : 0;
    }

    function applyDerivedFields(payload) {
        if (payload.application) {
            const employed = sectionValue(payload, "application", "DAYS_EMPLOYED");
            payload.application.DAYS_EMPLOYED_ANOM = employed === 365243 || employed === -365243 ? 1 : 0;
        }
        if (payload.bureau_agg) {
            setDerived(payload, "bureau_agg", "BUREAU_DEBT_TO_CREDIT_RATIO", ratio(
                sectionValue(payload, "bureau_agg", "BUREAU_AMT_CREDIT_SUM_DEBT_SUM"),
                sectionValue(payload, "bureau_agg", "BUREAU_AMT_CREDIT_SUM_SUM"),
            ));
        }
        if (payload.previous_agg) {
            const total = sectionValue(payload, "previous_agg", "PREV_APP_COUNT");
            setDerived(payload, "previous_agg", "PREV_APPROVAL_RATE", ratio(sectionValue(payload, "previous_agg", "PREV_APPROVED_COUNT"), total));
            setDerived(payload, "previous_agg", "PREV_REFUSAL_RATE", ratio(sectionValue(payload, "previous_agg", "PREV_REFUSED_COUNT"), total));
            setDerived(
                payload,
                "previous_agg",
                "PREV_APP_CREDIT_DIFF_MEAN",
                sectionValue(payload, "previous_agg", "PREV_AMT_APPLICATION_MEAN") - sectionValue(payload, "previous_agg", "PREV_AMT_CREDIT_MEAN"),
            );
            setDerived(payload, "previous_agg", "PREV_RATE_DOWN_PAYMENT_MEAN", 0);
        }
        if (payload.installments_agg) {
            setDerived(payload, "installments_agg", "INST_MISSED_RATE", ratio(
                sectionValue(payload, "installments_agg", "INST_LATE_COUNT"),
                sectionValue(payload, "installments_agg", "INST_RECORD_COUNT"),
            ));
            setDerived(payload, "installments_agg", "INST_PAYMENT_RATIO_MEAN", 0);
            setDerived(payload, "installments_agg", "INST_PAYMENT_RATIO_MIN", 0);
        }
        if (payload.credit_card_agg) {
            setDerived(payload, "credit_card_agg", "CC_UTILIZATION_MEAN", ratio(
                sectionValue(payload, "credit_card_agg", "CC_BALANCE_MEAN"),
                sectionValue(payload, "credit_card_agg", "CC_LIMIT_MEAN"),
            ));
            setDerived(payload, "credit_card_agg", "CC_PAYMENT_RATIO_MEAN", 0);
        }
        if (payload.upi_agg) {
            delete payload.upi_agg.balance_instability_score;
            delete payload.upi_agg.failed_due_to_low_balance;
            delete payload.upi_agg.failed_txn_count;
            delete payload.upi_agg.outflow_volatility;
            delete payload.upi_agg.inflow_volatility;
            delete payload.upi_agg.txn_value_std;
            delete payload.upi_agg.success_txn_count;
            delete payload.upi_agg.peak_txn_day_count;
        }
    }

    function buildPayload(form) {
        const payload = cloneValue((config.samplePayloads || {})[state.tier] || {});
        const sections = state.tier === "FULL"
            ? ["application", "bureau_agg", "previous_agg", "installments_agg", "pos_cash_agg", "credit_card_agg"]
            : state.tier === "UPI"
                ? ["upi_agg"]
                : ["application"];
        const missing = [];

        if (state.tier === "FULL") {
            sections
                .filter((sectionName) => sectionName !== "application")
                .forEach((sectionName) => {
                    payload[sectionName] = {};
                    FIELD_GROUPS[sectionName].forEach((fieldName) => {
                        payload[sectionName][fieldName] = 0;
                    });
                });
        }
        if (state.tier === "UPI") {
            payload.upi_agg = payload.upi_agg || {};
        }

        sections.forEach((sectionName) => {
            payload[sectionName] = payload[sectionName] || {};
            FIELD_GROUPS[sectionName].forEach((fieldName) => {
                if (DERIVED_FIELDS[sectionName] && DERIVED_FIELDS[sectionName].has(fieldName)) {
                    return;
                }
                const control = form.querySelector(`[data-section="${sectionName}"][name="${fieldName}"]`);
                if (!control) {
                    return;
                }

                const value = valueFromControl(control);
                if (value === null || value === "") {
                    if (sectionName === "application") {
                        missing.push(control);
                    } else if (state.tier === "FULL") {
                        payload[sectionName][fieldName] = 0;
                    } else {
                        missing.push(control);
                    }
                    return;
                }
                payload[sectionName][fieldName] = value;
            });
        });
        applyDerivedFields(payload);

        return {
            missing,
            payload,
        };
    }

    function enhanceFieldCopy(form) {
        form.querySelectorAll(".input-field").forEach((wrapper) => {
            const control = wrapper.querySelector("input, select");
            const label = wrapper.querySelector("label");
            if (!control || !label) {
                return;
            }
            const derived = DERIVED_FIELDS[control.dataset.section] && DERIVED_FIELDS[control.dataset.section].has(control.name);
            if (derived) {
                wrapper.classList.add("is-hidden");
                control.disabled = true;
                return;
            }
            const copy = FIELD_COPY[control.name];
            if (!copy) {
                label.textContent = control.name.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
                return;
            }
            label.textContent = copy[0];
            if (!wrapper.querySelector(".field-hint")) {
                const hint = document.createElement("p");
                hint.className = "field-hint";
                hint.textContent = copy[1];
                wrapper.appendChild(hint);
            }
        });
    }

    function renderMetadata(elements, response) {
        const rows = [
            ["Credit Score Range", "300-900"],
            ["Coverage Tier", response.coverage_tier || "-"],
            ["Calibrated", response.calibrated ? "Yes" : "No"],
            ["Fairness Audit", response.model_fairness_audit_passed ? "Passed" : "Not passed"],
            ["Model Version", response.model_version || "-", true],
        ];

        if (response.escalate) {
            rows.push(["Escalation Flag", "\u26a0 Referred for manual review"]);
        }

        elements.metadata.replaceChildren();
        rows.forEach((row) => {
            const item = document.createElement("div");
            item.className = "metadata-row";

            const label = document.createElement("span");
            label.className = "metadata-label";
            label.textContent = row[0];

            const value = document.createElement("span");
            value.className = row[2] ? "metadata-value monospace" : "metadata-value";
            value.textContent = row[1];

            item.append(label, value);
            elements.metadata.appendChild(item);
        });
    }

    function renderDrivers(elements, explanations) {
        elements.driverList.replaceChildren();
        (explanations || []).slice(0, 5).forEach((item) => {
            const row = document.createElement("div");
            row.className = "driver-row";

            const title = document.createElement("h3");
            title.textContent = item.feature || "Unknown feature";

            const reason = document.createElement("p");
            reason.textContent = item.reason || "No explanation was returned.";

            row.append(title, reason);
            elements.driverList.appendChild(row);
        });
    }

    function renderResult(elements, response) {
        elements.probability.textContent = formatCreditScore(response.probability_of_default, response.credit_score);
        elements.decision.textContent = response.decision || "REVIEW";
        elements.decision.className = `decision-pill ${decisionClass(response.decision)}`;
        renderMetadata(elements, response);
        renderDrivers(elements, response.top_5_explanations || []);

        elements.formStage.classList.add("is-hidden");
        elements.loadingStage.classList.add("is-hidden");
        elements.resultSection.classList.remove("is-hidden");
        elements.feedback.textContent = "";
    }

    async function submitAnalysis(elements) {
        clearValidation(elements.form);
        const built = buildPayload(elements.form);
        if (built.missing.length > 0) {
            built.missing.forEach(markInvalid);
            elements.feedback.textContent = "Complete all visible fields before submitting the application.";
            return;
        }

        elements.feedback.textContent = "";
        elements.formStage.classList.add("is-hidden");
        elements.loadingStage.classList.remove("is-hidden");
        elements.resultSection.classList.add("is-hidden");

        try {
            const response = await fetch(config.routes.score, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                },
                body: JSON.stringify(built.payload),
            });
            const body = await readJson(response);

            if (!response.ok) {
                throw new Error(body.message || "The scoring request failed.");
            }

            renderResult(elements, body);
        } catch (error) {
            elements.loadingStage.classList.add("is-hidden");
            elements.formStage.classList.remove("is-hidden");
            elements.feedback.textContent = error.message || "The scoring request failed.";
        }
    }

    function resetAnalysis(elements) {
        const currentTier = state.tier;
        elements.form.reset();
        clearValidation(elements.form);
        elements.feedback.textContent = "";
        elements.resultSection.classList.add("is-hidden");
        elements.loadingStage.classList.add("is-hidden");
        elements.formStage.classList.remove("is-hidden");
        setTier(currentTier, elements);
    }

    function initAnalyzePage() {
        const elements = {
            tierButtons: Array.from(document.querySelectorAll("[data-tier-toggle]")),
            tierDescription: document.getElementById("tier-description"),
            applicationFields: document.getElementById("application-fields"),
            bureauFields: document.getElementById("bureau-fields"),
            bureauDivider: document.getElementById("bureau-divider"),
            upiFields: document.getElementById("upi-fields"),
            upiDivider: document.getElementById("upi-divider"),
            form: document.getElementById("analysis-form"),
            formStage: document.getElementById("analysis-form-stage"),
            loadingStage: document.getElementById("analysis-loading-stage"),
            resultSection: document.getElementById("analysis-result"),
            scoreButton: document.getElementById("score-button"),
            scoreAnother: document.getElementById("score-another"),
            feedback: document.getElementById("analysis-feedback"),
            probability: document.getElementById("result-probability"),
            decision: document.getElementById("result-decision"),
            metadata: document.getElementById("result-metadata"),
            driverList: document.getElementById("driver-list"),
        };

        enhanceFieldCopy(elements.form);

        elements.tierButtons.forEach((button) => {
            button.addEventListener("click", function () {
                setTier(button.dataset.tier, elements);
            });
        });
        elements.scoreButton.addEventListener("click", function () {
            submitAnalysis(elements);
        });
        elements.scoreAnother.addEventListener("click", function () {
            resetAnalysis(elements);
        });

        elements.form.querySelectorAll("input, select").forEach((control) => {
            control.addEventListener("input", function () {
                control.classList.remove("invalid");
                control.removeAttribute("aria-invalid");
            });
            control.addEventListener("change", function () {
                control.classList.remove("invalid");
                control.removeAttribute("aria-invalid");
            });
        });

        setTier("REDUCED", elements);
    }

    function applyStatusHealth(health) {
        const system = document.getElementById("status-system");
        const version = document.getElementById("status-version");
        const fairness = document.getElementById("status-fairness");
        const tiers = document.getElementById("status-tiers");
        const error = document.getElementById("status-error");

        if (!system || !version || !fairness || !tiers || !error) {
            return;
        }

        if (!health) {
            error.classList.remove("is-hidden");
            system.innerHTML = '<span class="status-dot degraded"></span>Degraded';
            fairness.textContent = "Not passed";
            fairness.className = "status-value fairness-fail";
            version.textContent = "Unavailable";
            tiers.textContent = "Unavailable";
            return;
        }

        error.classList.add("is-hidden");
        system.innerHTML = health.status === "ok"
            ? '<span class="status-dot ok"></span>Operational'
            : '<span class="status-dot degraded"></span>Degraded';
        version.textContent = health.model_version || "Unavailable";
        fairness.textContent = health.fairness_audit_passed ? "Passed" : "Not passed";
        fairness.className = health.fairness_audit_passed
            ? "status-value fairness-pass"
            : "status-value fairness-fail";
        tiers.textContent = (health.coverage_tiers_available || []).join(", ") || "Unavailable";
    }

    async function initStatusPage() {
        applyStatusHealth(initialHealth);
        try {
            const response = await fetch(config.routes.health, {
                headers: {
                    Accept: "application/json",
                },
            });
            if (!response.ok) {
                throw new Error("Health check failed.");
            }
            const body = await readJson(response);
            applyStatusHealth(body);
        } catch (error) {
            applyStatusHealth(null);
        }
    }

    window.addEventListener("scroll", navScrollState, { passive: true });
    navScrollState();
    initThemeToggle();

    if (page === "analyze") {
        initAnalyzePage();
    }

    if (page === "status") {
        initStatusPage();
    }
})();
