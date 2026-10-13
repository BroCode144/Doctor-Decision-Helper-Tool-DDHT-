import { createContext, useContext, useState } from "react";
import { useData } from "./DataContext";

const AuthContext = createContext(null);

const STORAGE_KEY = "ddht_session";

export function AuthProvider({ children }) {
  const { users } = useData();
  const [user, setUser] = useState(() => {
    try {
      const stored = sessionStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });

  const login = (email, password) => {
    const match = users.find(
      (u) => u.email.toLowerCase() === email.trim().toLowerCase() && u.password === password
    );

    if (!match) {
      return { success: false, error: "Invalid email or password." };
    }

    if (match.status === "Inactive") {
      return {
        success: false,
        error: "This account has been deactivated. Contact an administrator.",
      };
    }

    const session = {
      id: match.id,
      email: match.email,
      role: match.role,
      name: match.name,
      linkedId: match.linkedId,
    };

    setUser(session);
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } catch {
      // sessionStorage unavailable — session stays in-memory only
    }
    return { success: true, user: session };
  };

  const logout = () => {
    setUser(null);
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
