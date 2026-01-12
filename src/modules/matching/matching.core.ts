/**
 * Purpose: Core logic for matching algorithms.
 * Overview: Pure functions for scoring and deal breaker checks.
 */

export interface HelperProfile {
    preferences: Record<string, any>;
    dealBreakers: Record<string, any>;
}

export const calculateScore = (a: HelperProfile, b: HelperProfile): number => {
    const keysA = Object.keys(a.preferences);
    const keysB = Object.keys(b.preferences);
    const allKeys = new Set([...keysA, ...keysB]);

    if (allKeys.size === 0) return 0;

    let matches = 0;
    allKeys.forEach(key => {
        const valA = a.preferences[key];
        const valB = b.preferences[key];

        if (valA !== undefined && valB !== undefined && valA === valB) {
            matches++;
        }
    });

    return (matches / allKeys.size) * 100;
}

export const hasDealBreaker = (a: HelperProfile, b: HelperProfile): boolean => {
    // Check A's breakers against B
    for (const [key, reqVal] of Object.entries(a.dealBreakers)) {
        // If B has the attribute and it doesn't match requirement -> BREAK
        if (b.preferences[key] !== undefined && b.preferences[key] !== reqVal) {
            return true;
        }
    }

    // Check B's breakers against A
    for (const [key, reqVal] of Object.entries(b.dealBreakers)) {
        if (a.preferences[key] !== undefined && a.preferences[key] !== reqVal) {
            return true;
        }
    }

    return false;
}
