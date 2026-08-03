// Thrown when a request references another resource (a departmentId, a
// reportsToRoleId, ...) that either doesn't exist or belongs to a different
// company. Distinct from "the resource you asked to GET doesn't exist"
// (which route handlers represent with a plain `null` return + 404) because
// this one means the *input* was bad, so it maps to 400.
export class InvalidReferenceError extends Error {}
