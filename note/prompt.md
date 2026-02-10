
We want to develop autopilot bot which do by openclaw ai. start by run 1 job then set crontab to do wakeup in next minute to find better strategy

objective: find strategy to beat the market (buy_and_hold)
coding dir: sub path ./alice_checking

each job should create clear file about job plan , result 
write example of each job file.
user can easy see the progress result

job should be run all etf in parallel job e.g. python processPoolExecuture.

1. develop first job as reference: buy_hold_stratgy
  use ./core/  for fetch data
  use ./data/etf-v3.yaml as list of etf
   ./result use to store data but should have sub_folder 'alice_checking' to store
2. create plan.md , to tell the openclaw ai to do. 


do not need to read another folder
  
