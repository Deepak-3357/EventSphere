import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getSupabaseClient, getVerifiedIdentity, signOut } from "./auth-client.js";

const AuthContext = createContext({ session: null, profile: null, loading: true });

export function AuthProvider({ children }) {
  const [identity, setIdentity] = useState({ session: null, profile: null, loading: true });

  useEffect(() => {
    let active = true;
    getVerifiedIdentity()
      .then(({ session, profile }) => active && setIdentity({ session, profile, loading: false }))
      .catch(() => active && setIdentity({ session: null, profile: null, loading: false }));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let unsubscribe;
    getSupabaseClient().then((client) => {
      const result = client.auth.onAuthStateChange(() => {
        getVerifiedIdentity().then(({ session, profile }) => setIdentity({ session, profile, loading: false })).catch(() => setIdentity({ session: null, profile: null, loading: false }));
      });
      unsubscribe = result.data.subscription.unsubscribe;
    }).catch(() => {});
    return () => unsubscribe?.();
  }, []);

  const value = useMemo(() => ({ ...identity, signOut: async () => { await signOut(); setIdentity({ session: null, profile: null, loading: false }); } }), [identity]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
