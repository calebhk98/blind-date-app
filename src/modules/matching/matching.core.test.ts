/**
 * Purpose: Tests for Core Matching Logic.
 * Overview: Unit tests for calculateScore and hasDealBreaker using mock data.
 */
import { calculateScore, hasDealBreaker, HelperProfile } from './matching.core'

// Helper Objects
const pEmpty: HelperProfile = { preferences: {}, dealBreakers: {} }
const pSmoker: HelperProfile = { preferences: { smoker: true }, dealBreakers: {} }
const pNonSmoker: HelperProfile = { preferences: { smoker: false }, dealBreakers: {} }

describe('calculateScore', () => {
    // Happy 1
    it('returns 100 for exact match on all keys', () => {
        const p1: HelperProfile = { preferences: { a: 1, b: 2 }, dealBreakers: {} }
        const p2: HelperProfile = { preferences: { a: 1, b: 2 }, dealBreakers: {} }
        expect(calculateScore(p1, p2)).toBe(100)
    })

    // Happy 2
    it('returns 0 for completely disjoint preferences', () => {
        const p1: HelperProfile = { preferences: { a: 1 }, dealBreakers: {} }
        const p2: HelperProfile = { preferences: { b: 2 }, dealBreakers: {} }
        expect(calculateScore(p1, p2)).toBe(0)
    })

    // Happy 3
    it('returns partial score for partial match', () => {
        const p1: HelperProfile = { preferences: { a: 1, b: 2 }, dealBreakers: {} }
        const p2: HelperProfile = { preferences: { a: 1, b: 3 }, dealBreakers: {} }
        // a matches (50%), b mismatch. Score 50?
        expect(calculateScore(p1, p2)).toBe(50)
    })

    // Fail/Edge 1
    it('returns 0 if both empty', () => {
        expect(calculateScore(pEmpty, pEmpty)).toBe(0)
    })

    // Fail/Edge 2
    it('handles boolean values', () => {
        expect(calculateScore(pSmoker, pSmoker)).toBe(100)
        expect(calculateScore(pSmoker, pNonSmoker)).toBe(0)
    })
})

describe('hasDealBreaker', () => {
    // Schema: dealBreakers: { key: requiredValue }
    // If other.preferences[key] !== requiredValue => Break.

    // Happy 1
    it('returns false (safe) when no deal breakers', () => {
        expect(hasDealBreaker(pEmpty, pEmpty)).toBe(false)
    })

    // Happy 2: A requires smoker=false, B is smoker=true => True (Break)
    it('returns true when A dealbreaker is violated by B', () => {
        const pA: HelperProfile = { preferences: {}, dealBreakers: { smoker: false } }
        const pB: HelperProfile = { preferences: { smoker: true }, dealBreakers: {} }
        expect(hasDealBreaker(pA, pB)).toBe(true)
    })

    // Happy 3: B requires smoker=false, A is smoker=true => True (Break)
    it('returns true when B dealbreaker is violated by A', () => {
        const pA: HelperProfile = { preferences: { smoker: true }, dealBreakers: {} }
        const pB: HelperProfile = { preferences: {}, dealBreakers: { smoker: false } }
        expect(hasDealBreaker(pA, pB)).toBe(true)
    })

    // Happy 4: A requires smoker=true, B is smoker=true => False (Safe)
    it('returns false when dealbreaker requirement is met', () => {
        const pA: HelperProfile = { preferences: {}, dealBreakers: { smoker: true } }
        const pB: HelperProfile = { preferences: { smoker: true }, dealBreakers: {} }
        expect(hasDealBreaker(pA, pB)).toBe(false)
    })

    // Fail/Edge 1: Missing key in preference treated as mismatch -> True (Break) or False (Ignore)?
    // "What deal breaker can you tell in 5 messages..."
    // If I say "Must be tall", and they don't say height -> ?
    // Let's assume STRICT: If missing, it's a breaker (or maybe ignore?).
    // For now, let's assume if key is missing in preference, we can't verify, so maybe False (don't break yet) or True (Safety).
    // Let's define: Missing key = Not broken (False) for MVP.
    it('returns false if key is missing in target preferences', () => {
        const pA: HelperProfile = { preferences: {}, dealBreakers: { age: 25 } }
        const pB: HelperProfile = { preferences: {}, dealBreakers: {} } // No age
        expect(hasDealBreaker(pA, pB)).toBe(false)
    })
})
