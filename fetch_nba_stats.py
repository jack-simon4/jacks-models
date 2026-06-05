from nba_api.stats.static import teams
from nba_api.stats.endpoints import leaguedashteamstats
import pandas as pd

# Fetch all teams
nba_teams = teams.get_teams()

# Example: Print all teams
print("NBA Teams:", nba_teams)

# Fetch league-wide team stats for the current season
team_stats = leaguedashteamstats.LeagueDashTeamStats()

# Convert response to a pandas DataFrame
df = team_stats.get_data_frames()[0]

# Save the stats to a CSV file
df.to_csv('NBA-Team-Stats.csv', index=False)

print("Data saved to NBA-Team-Stats.csv")
