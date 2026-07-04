import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Projects from "./pages/Projects";
import ProjectDetail from "./pages/ProjectDetail";

function PrivateRoute({ children }: { children: React.ReactNode }) {
return localStorage.getItem("token") ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
return (
    <BrowserRouter>
    <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<PrivateRoute><Projects /></PrivateRoute>} />
        <Route path="/projects/:id" element={<PrivateRoute><ProjectDetail /></PrivateRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </BrowserRouter>
);
}
