i want to use claude to research for me
call it 1 time for research 1 year  .
i want to research from 2012 to 2025

step.
1 change pwd to /home/zoftdev/clawd/workspace/etf/macro-forecast-claude
2. run claude -p  "do @prompt.md for 2012"  
change year to the end year(2012,2013)  each time you request
3. check return code /message  if success then continue next year
4. if fail then  set crontab to do in next 10 minute
5. note the start,next,stop year in alice-note.json 
6. next time check next in note file to redo