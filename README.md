# HHbbVV

For [coffea-casa](https://coffea-casa.readthedocs.io/en/latest/cc_user.html) (from the coffea-casa binder):
1. open `runCoffeaCasa.ipynb` 
2. import your desired processor, specify it in the `run_uproot_job` function, and specify your filelist
3. run the first three cells


To submit with normal condor:

```
git clone https://github.com/rkansal47/HHbbVV/
cd HHbbVV
git checkout condor
# replace 'rkansal' in homedir var in condor/submit.py and the proxy address in condor/submit.templ.jdl 
python condor/submit.py Jul1 run.py 20  # will need python3
for i in condor/Jul1/*.jdl; do condor_submit $i; done
```




TODO: instructions for lpcjobqueue (currently quite buggy)
