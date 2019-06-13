from scipy.special import erfinv
import alliance_models
import event_types
import award_types
import slff_points
import tbapy
import math
import os


class ScoreSLFF:
    def __init__(self):
        # TODO make this work on more than just my machines?
        self.tba = tbapy.TBA(os.getenv("TBA_KEY"))

    def score_event(self, event_key, include_alliances=True, alliance_model=alliance_models.default):
        event_info = self.tba.event(event_key)
        event_ranks = self.tba.event_rankings(event_key)['rankings']
        event_alliances = self.tba.event_alliances(event_key)
        event_matches = self.tba.event_matches(event_key)
        event_awards = self.tba.event_awards(event_key)

        team_count = len(event_ranks)
        points_dict = {}

        # Intentionally using event RANKS - not event TEAMS - since teams listed as attending and not playing happens.
        for team in event_ranks:
            # This sets up dict entries for all teams at the event and gives them quals points.
            points_dict[team['team_key']] = {'quals': self.quals_points(team['rank'], team_count),
                                             'awards': 0,
                                             'draft': 0,
                                             'elims': 0}

        # Only add award points for official events that have awards
        if event_awards and event_info.event_type in event_types.OFFICIAL:
            # If event type is champs div or champs finals then use those points, otherwise normal points
            award_points = slff_points.CHAMPS if event_info.event_type in event_types.CHAMPS else slff_points.NORMAL

            for award in event_awards:
                for team in award['recipient_list']:
                    # Awards like VOTY might not have a team key.
                    if team['team_key']:
                        # Handles teams that win awards without playing matches
                        if not team['team_key'] in points_dict:
                            points_dict[team['team_key']] = {'quals': 0, 'awards': 0, 'draft': 0, 'elims': 0}
                        points_dict[team['team_key']]['awards'] += award_points[award['award_type']]

                        # This handles "5 points for making Einstein finals regardless of play"
                        if event_info.event_type == event_types.CMP_FINALS:
                            if award['award_type'] in [award_types.FINALIST, award_types.WINNER]:
                                points_dict[team['team_key']]['awards'] += 5
        else:
            # Either not an official event or else there isn't awards data yet
            pass

        # For non-quals matches award five points to each playing member of the winning alliance
        for match in event_matches:
            if match.comp_level != 'qm':
                try:
                    for team in match.alliances[match.winning_alliance]['team_keys']:
                        team_val = team.split(" ")[0]  # This is just to handle "58 /" at 2019wiwi, remove later?
                        points_dict[team_val]['elims'] += 5
                except KeyError:
                    # This catches un-played matches that are registered with TBA. Example: 2019wiwi_f2m1
                    pass

        if include_alliances:
            for idx, alliance in enumerate(event_alliances):
                for pick, team in enumerate(alliance.picks):
                    points_dict[team]['draft'] += alliance_model[idx + 1][pick]

        # Converts the dictionary into a list of dict
        team_points = []
        for team_key in points_dict:
            team_dict = points_dict[team_key]
            team_dict['team_key'] = team_key
            team_dict['total'] = team_dict['quals'] + team_dict['elims'] + team_dict['draft'] + team_dict['awards']
            team_points.append(team_dict)

        return team_points

    # noinspection PyTypeChecker
    @staticmethod
    def quals_points(team_rank, team_count):
        alpha = 1.07
        return math.ceil(abs(erfinv((team_count - 2 * team_rank + 2) / (alpha * team_count))
                             * 10 / erfinv(1 / alpha) + 12))


if __name__ == '__main__':
    scorer = ScoreSLFF()
    event_scores = sorted(scorer.score_event('2019necmp'), key=lambda k: k['total'], reverse=True)

    for entry in event_scores:
        print(entry)
