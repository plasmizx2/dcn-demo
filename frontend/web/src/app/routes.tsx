import { createBrowserRouter } from "react-router";
import { LandingPage } from "./pages/landing";
import { LoginPage } from "./pages/login";
import { SubmitJobPage } from "./pages/submit-job";
import { MyJobsPage } from "./pages/my-jobs";
import { DashboardPage } from "./pages/dashboard";
import { Navigate, useLocation } from "react-router";
import { AllJobsPage } from "./pages/all-jobs";

function RedirectResultsToJobs() {
  const { hash } = useLocation();
  return <Navigate to={`/jobs${hash}`} replace />;
}
import { WorkerLogsPage } from "./pages/worker-logs";
import { AdminUsersPage } from "./pages/admin-users";
import { ContactPage } from "./pages/contact";
import { ReportBugPage } from "./pages/report-bug";
import { NotFoundPage } from "./pages/not-found";
import { WaitlistPage } from "./pages/waitlist";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: LandingPage,
  },
  {
    path: "/login",
    Component: LoginPage,
  },
  {
    path: "/submit",
    Component: SubmitJobPage,
  },
  {
    path: "/my-jobs",
    Component: MyJobsPage,
  },
  {
    path: "/ops",
    Component: DashboardPage,
  },
  {
    path: "/jobs",
    Component: AllJobsPage,
  },
  {
    path: "/results",
    Component: RedirectResultsToJobs,
  },
  {
    path: "/worker-logs",
    Component: WorkerLogsPage,
  },
  {
    path: "/admin/users",
    Component: AdminUsersPage,
  },
  {
    path: "/contact",
    Component: ContactPage,
  },
  {
    path: "/report-bug",
    Component: ReportBugPage,
  },
  {
    path: "/waitlist",
    Component: WaitlistPage,
  },
  {
    path: "*",
    Component: NotFoundPage,
  },
]);
