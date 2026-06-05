import requests

def get_team_odds(team_name, data):
    team_odds = {}

    for match in data:
        home_team = match["home_team"]
        away_team = match["away_team"]

        # Check if the given team is playing in the match
        if team_name == home_team or team_name == away_team:
            for bookmaker in match["bookmakers"]:
                markets = bookmaker["markets"]

                for market in markets:
                    if "h2h" in market["key"]:
                        outcomes = market["outcomes"]

                        for outcome in outcomes:
                            outcome_name = outcome["name"]
                            odds = outcome["price"]

                            # Store the odds for the given team
                            if outcome_name == team_name:
                                team_odds[home_team] = odds if outcome_name == home_team else team_odds.get(home_team, odds)
                                team_odds[away_team] = odds if outcome_name == away_team else team_odds.get(away_team, odds)

    return team_odds

# API endpoint
api_url = "https://api.the-odds-api.com/v4/sports/upcoming/odds/?regions=us&markets=h2h&oddsFormat=american&apiKey=c1f8fd1cdb38f9d480275f968eca2511"

# Fetch data from the API
response = requests.get(api_url)
your_data = response.json()

# Check if there are events in the response
if "price" in your_data:
    events_data = your_data["price"]
    team_name = "Tunisia"  # Replace with the desired team name
    team_odds = get_team_odds(team_name, events_data)

    # Print the odds for the team in each match
    for team, odds in team_odds.items():
        print(f"{team} odds to win: {odds}")
else:
    print("No data found in the API response.")
