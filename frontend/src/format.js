export const fmtDate = (v) =>
  v ? new Date(v).toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" }) : "—";

export const fmtDateTime = (v) =>
  v
    ? new Date(v).toLocaleString("en-KE", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })
    : "—";

export const fmtNum = (v, digits = 0) =>
  v === null || v === undefined ? "—" : Number(v).toLocaleString("en-KE", { maximumFractionDigits: digits });

export const titleCase = (s) => (s || "").toLowerCase().replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export const ID_TYPES = [
  ["NATIONAL_ID", "National ID"],
  ["MAISHA_NAMBA", "Maisha Namba"],
  ["BIRTH_CERT", "Birth certificate"],
  ["PASSPORT", "Passport"],
  ["REFUGEE_ID", "Refugee ID"],
];

export const ACK_REASONS = [
  ["CLINICALLY_JUSTIFIED", "Clinically justified"],
  ["VERIFIED_WITH_PRESCRIBER", "Verified with prescriber"],
  ["PATIENT_LOST_MEDICATION", "Patient lost medication"],
  ["DOSE_CHANGE", "Dose change / new regimen"],
  ["PALLIATIVE_CARE", "Palliative / cancer care"],
  ["OTHER", "Other (note required)"],
];

export const ROLE_LABEL = {
  PRESCRIBER: "Prescriber",
  PHARMACIST: "Pharmacist",
  REGULATOR: "County regulator",
  SYSTEM_ADMIN: "System admin",
  FACILITY_ADMIN: "Facility admin",
};
