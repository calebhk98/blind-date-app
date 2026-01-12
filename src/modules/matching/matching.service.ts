/**
 * Purpose: Service for Orchestrating Matching process.
 * Overview: Fetches users, runs core logic, creates matches using Repositories.
 */
import { calculateScore, hasDealBreaker, HelperProfile } from './matching.core'
import { IUserRepository, IMatchRepository } from '@/repositories/interfaces'

export class MatchingService {
    constructor(
        private userRepo: IUserRepository,
        private matchRepo: IMatchRepository
    ) { }

    async findAndCreateMatches() {
        // Fetch active users with positive credits and profiles
        const usersWithProfile = await this.userRepo.findActiveUsersWithCredits();

        const matchedIds = new Set<string>();
        let matchCount = 0;

        for (let i = 0; i < usersWithProfile.length; i++) {
            const userA = usersWithProfile[i];
            if (matchedIds.has(userA.id)) continue;

            let bestMatch = null;
            let bestScore = -1;

            const profileA = userA.profile!;
            let helperA: HelperProfile;
            try {
                helperA = {
                    preferences: JSON.parse(profileA.preferences),
                    dealBreakers: JSON.parse(profileA.dealBreakers)
                };
            } catch (e) {
                console.error(`Invalid JSON for user ${userA.id}`);
                continue;
            }

            for (let j = i + 1; j < usersWithProfile.length; j++) {
                const userB = usersWithProfile[j];
                if (matchedIds.has(userB.id)) continue;

                // Check existing match logic
                const existing = await this.matchRepo.findExisting(userA.id, userB.id);
                if (existing) continue;

                const profileB = userB.profile!;
                let helperB: HelperProfile;
                try {
                    helperB = {
                        preferences: JSON.parse(profileB.preferences),
                        dealBreakers: JSON.parse(profileB.dealBreakers)
                    };
                } catch (e) {
                    continue;
                }

                if (hasDealBreaker(helperA, helperB)) continue;

                const score = calculateScore(helperA, helperB);

                // Greedy Best Match
                if (score > bestScore) {
                    bestScore = score;
                    bestMatch = userB;
                }
            }

            if (bestMatch) {
                await this.matchRepo.create({
                    userAId: userA.id,
                    userBId: bestMatch.id,
                    score: bestScore,
                    status: 'PENDING'
                });
                matchedIds.add(userA.id);
                matchedIds.add(bestMatch.id);
                matchCount++;
            }
        }

        return matchCount;
    }
}
