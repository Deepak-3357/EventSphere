export const roleHomePaths = {
  student: "/student/",
  organizer: "/organizer/",
  admin: "/admin/",
};

export function roleHomePath(role) {
  return roleHomePaths[role] || "/";
}
