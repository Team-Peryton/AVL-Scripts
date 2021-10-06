from typing import Counter
from avl_aero_coefficients import Aero
from geometry import Plane,Section
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from multiprocessing import freeze_support
import matplotlib.pyplot as plt
import pandas as pd
import numpy
import math
import os
import shutil
import time
from tqdm import tqdm

def load_inputs(input_file):
    with open(input_file,'r') as f:
        lines=f.readlines()
    
    inputs={"input_plane":lines[1].split()[1],
            "aero_config":lines[2].split()[1],
            "wing_aerofoil":lines[4].split(": ")[1:][0],
            "elevator_aerofoil":lines[5].split(": ")[1:][0],
            "fin_aerofoil":lines[6].split(": ")[1:][0],
            "angle_min":float(lines[9].split()[1]),
            "angle_max":float(lines[10].split()[1]),
            "increment":int(lines[11].split()[1]),
            "span_loc":float(lines[13].split()[1]),
            "threads":float(lines[15].split()[1])}

    return inputs

def load_plane(input_plane:str):
    with open(input_plane,'r') as f:
        plane_geom=[line for line in f.readlines()  if line!="\n" and line[0]!="#"]
    
    ref_dims=[line for line in plane_geom][3]
    mac=float(ref_dims.split()[1])
    span=float(ref_dims.split()[2])

    return plane_geom, mac, span

def run(input_file):
    inputs=load_inputs(input_file)
    plane_geom,mac,span=load_plane(inputs["input_plane"])
    ref_plane_geom,ref_plane=make_ref_plane(plane_geom,mac,span,inputs["span_loc"],inputs["wing_aerofoil"])

    planes=generate_planes(ref_plane_geom,inputs["angle_min"],inputs["angle_max"],inputs["increment"],inputs["span_loc"],span,ref_plane,mac,inputs["wing_aerofoil"])
    analysis=Aero(inputs["aero_config"])
    cases=[case for case in analysis.initialize_cases()]    #   Generates & writes cases
    #cases is unique
    tasks=[]
    count=0
    for plane in planes:
        plane.cases=cases
        for case in plane.cases:
            case.id=count
            count+=1
            #count is unique
            tasks.append([plane,case,analysis])
            #tasks are unique

    #tasks=[(plane,case,analysis) for plane in planes for case in cases]

    print("Analysing...")
    with ThreadPoolExecutor(max_workers=inputs["threads"]) as pool:
        #list(tqdm(pool.map(run_analysis,tasks),total=len(tasks)))
        pool.map(run_analysis,tasks)
    """
    for plane in planes:
        print(plane.name)
        for case in plane.cases:
            print(case.results_file)
"""
    tasks=[plane for plane in planes]
    with ThreadPoolExecutor(max_workers=inputs["threads"]) as pool:
        pool.map(polars,tasks)

    pass

def make_ref_plane(plane_geom:list,mac,span,span_loc,wing_aerofoil)->tuple:
    ref_plane=Plane("reference",mac=mac)
    split_Yle=(span/2)*(span_loc/100)
    ref_plane_geom=ref_plane.make_dihedral_ref(plane_geom,split_Yle,wing_aerofoil)

    return tuple(ref_plane_geom), ref_plane

def generate_planes(ref_plane_geom:list,angle_min,angle_max,increment,span_loc,span,ref_plane,mac,aerofoil):
    t0=time.time()
    planes=[]
    count=0
    hspan=span/2
    split_loc=hspan*span_loc/100

    for angle in numpy.linspace(angle_min,
                                angle_max,
                                int(1+(angle_max-angle_min)/increment)):

        name="".join([str(count),"-",str(angle),"Theta-",str(span_loc),"%"])
        plane=Plane(name)
        plane.d_theta=angle

        mod_geom=list(ref_plane_geom)

        Zle=round((hspan-split_loc)*math.sin(math.radians(angle)),3)
        Yle=round((hspan-split_loc)*math.cos(math.radians(angle))+split_loc,3)

        tip=Section(ref_plane.Xle,Yle,Zle,mac,19,-2,aerofoil)
        mod_str=tip.create_input()

        for index,line in enumerate(mod_geom):
            if line=="YES PLEASE\n":
                mod_geom.pop(index)
                mod_geom.insert(index,mod_str)
            
        plane.geom_file="generated planes/"+plane.name+".avl"
        with open(plane.geom_file,'w') as file:
            file.write("".join(mod_geom))
        count+=1

        planes.append(plane)
        plane.results_file=list()

    print("Planes generated...")
    return(planes)

def run_analysis(tasks):
    #time.sleep(0.001)
    plane,case,analysis=tasks
    print(case.id)
    analysis.analysis(plane,case)
    
    pass

def polars(plane):
    Aero.results(plane)

def plot(alpha:list,lift:list,drag:list):
    plt.figure(figsize=(10, 4))

    plt.subplot(121)
    plt.xlabel("Alpha (deg)")
    plt.ylabel("Cl")
    plt.plot(alpha, lift)
    plt.subplot(122)
    plt.xlabel("Alpha (deg)")
    plt.ylabel("Cd")
    plt.plot(alpha, drag)
    plt.suptitle('Polars')

    lift_polar=pd.DataFrame(data={'alpha':alpha,'lift':lift})
    drag_polar=pd.DataFrame(data={'alpha':alpha,'drag (avl)':drag})
    #lift_polar.to_excel("lift_polar.xlsx")
    #drag_polar.to_excel("drag_polar.xlsx")

    plt.show()

if __name__=='__main__':
    os.system('cls')
    freeze_support()

    path=os.path.abspath(os.getcwd())
    if os.path.isdir(path+"/results")==True:
        shutil.rmtree(path+"/results")
    if os.path.isdir(path+"/generated planes")==True:
        shutil.rmtree(path+"/generated planes")
    os.mkdir(path+"/generated planes")
    os.mkdir(path+"/results")

    input_file="DIHEDRAL_CONFIG.txt"

    run(input_file)