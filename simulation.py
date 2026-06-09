import simpy
import random
import numpy as np
import matplotlib.pyplot as plt
import time

# ==========================================
# 1. Physical Factory Layout Coordinates (X, Y)
# ==========================================
POS_ASRS  = np.array([1.5, 5.0])    # Central Automated Storage and Retrieval System
POS_WIP   = np.array([5.0, 1.5])    # WIP (Work-in-Process) Buffer Area
POS_CNC_B = np.array([8.5, 7.5])    # Core Bottleneck Station: CNC B
POS_CNC_C = np.array([8.5, 4.5])    # Standard Station: CNC C
POS_QC    = np.array([5.0, 8.5])    # Quality Control & Exit Station (Sink)

# Simulation Speed Parameter: Pause duration in seconds per frame
FRAME_SPEED = 0.02 

# ==========================================
# 2. Object-Oriented Mobile Resource (AGV Class)
# ==========================================
class AGVEntity:
    def __init__(self, agv_id):
        self.id = agv_id
        self.pos = POS_ASRS.copy()
        self.status = "IDLE"          # IDLE, TRAVEL_EMPTY, TRAVEL_LOAD
        self.target_pos = POS_ASRS.copy()
        self.start_pos = POS_ASRS.copy()
        self.move_start_time = 0.0
        self.move_end_time = 0.0
        self.has_load = False

    def assign_task(self, env, from_pos, to_pos, duration):
        """Simulate AGV logistics handling task"""
        self.start_pos = self.pos.copy()
        self.target_pos = from_pos
        self.status = "TRAVEL_EMPTY"
        self.move_start_time = env.now
        self.move_end_time = env.now + duration * 0.4 # Empty travel time
        yield env.timeout(duration * 0.4)
        
        # Arrive at pickup point, load material
        self.pos = from_pos.copy()
        self.start_pos = from_pos.copy()
        self.target_pos = to_pos
        self.status = "TRAVEL_LOAD"
        self.has_load = True
        self.move_start_time = env.now
        self.move_end_time = env.now + duration * 0.6 # Loaded travel time
        yield env.timeout(duration * 0.6)
        
        # Arrive at destination, unload material
        self.pos = to_pos.copy()
        self.status = "IDLE"
        self.has_load = False

    def update_position(self, current_time):
        """Linearly interpolate AGV coordinates for smooth animation"""
        if self.status != "IDLE":
            total_duration = self.move_end_time - self.move_start_time
            if total_duration > 0:
                fraction = (current_time - self.move_start_time) / total_duration
                fraction = min(max(fraction, 0.0), 1.0)
                self.pos = self.start_pos + fraction * (self.target_pos - self.start_pos)

# ==========================================
# 3. Simulation Logic & Core Performance Metrics
# ==========================================
class FactorySystem:
    def __init__(self, env, num_agvs):
        self.env = env
        # Static Resources: Machines (Arena Resource Module)
        self.cnc_b = simpy.Resource(env, capacity=1)
        self.cnc_c = simpy.Resource(env, capacity=1)
        # Mobile Resources: AGV Fleet
        self.agv_fleet = [AGVEntity(i) for i in range(num_agvs)]
        self.agv_resource = simpy.Resource(env, capacity=num_agvs)
        
        # Real-time KPI Statistics (Dashboard Data)
        self.total_output = 0
        self.cnc_b_waits = []
        self.cnc_c_waits = []
        self.total_agv_busy_time = 0.0

    def find_idle_agv(self):
        for agv in self.agv_fleet:
            if agv.status == "IDLE":
                return agv
        return self.agv_fleet[0]

    def workpiece_flow(self, wp_id):
        """State machine for a single workpiece routing"""
        # Routing Decision: 65% to bottleneck B, 35% to standard C
        target_station = "B" if random.random() < 0.65 else "C"
        target_resource = self.cnc_b if target_station == "B" else self.cnc_c
        dest_pos = POS_CNC_B if target_station == "B" else POS_CNC_C
        
        # --------- Stage 1: Request AGV to move from ASRS to CNC ---------
        with self.agv_resource.request() as agv_req:
            yield agv_req
            active_agv = self.find_idle_agv()
            travel_time = random.uniform(3.0, 5.0)
            self.total_agv_busy_time += travel_time
            yield self.env.process(active_agv.assign_task(self.env, POS_ASRS, dest_pos, travel_time))

        # --------- Stage 2: Adaptive CDF Rerouting Decision ---------
        while True:
            current_queue = len(target_resource.queue)
            if current_queue >= 3:
                # Buffer congested: 75% chance to redirect to WIP buffer
                if random.random() < 0.75:
                    with self.agv_resource.request() as agv_req:
                        yield agv_req
                        active_agv = self.find_idle_agv()
                        self.total_agv_busy_time += 2.0
                        yield self.env.process(active_agv.assign_task(self.env, dest_pos, POS_WIP, 2.0))
                    
                    # Stay in WIP temporary rack
                    yield self.env.timeout(random.uniform(10.0, 18.0))
                    
                    # Request AGV to move from WIP back to CNC decision point
                    with self.agv_resource.request() as agv_req:
                        yield agv_req
                        active_agv = self.find_idle_agv()
                        self.total_agv_busy_time += 2.0
                        yield self.env.process(active_agv.assign_task(self.env, POS_WIP, dest_pos, 2.0))
                    continue # Re-enter loop to check buffer length again
            break

        # --------- Stage 3: Seize Machine & Process (Delay) ---------
        queue_start = self.env.now
        with target_resource.request() as cnc_req:
            yield cnc_req
            wait_time = self.env.now - queue_start
            if target_station == "B":
                self.cnc_b_waits.append(wait_time)
            else:
                self.cnc_c_waits.append(wait_time)
            
            # Machine processing delay (Arena Delay)
            process_time = random.uniform(12.0, 26.0) if target_station == "B" else random.uniform(10.0, 18.0)
            yield self.env.timeout(process_time)

        # --------- Stage 4: Request AGV to move to QC & Dispose ---------
        with self.agv_resource.request() as agv_req:
            yield agv_req
            active_agv = self.find_idle_agv()
            travel_time = random.uniform(2.0, 4.0)
            self.total_agv_busy_time += travel_time
            yield self.env.process(active_agv.assign_task(self.env, dest_pos, POS_QC, travel_time))
            
        yield self.env.timeout(random.uniform(2.0, 4.0)) # QC Inspection time
        self.total_output += 1

def source_generator(env, factory):
    """Workpiece Arrival Generator (Arena Create Module)"""
    wp_id = 0
    while True:
        # Fixed: Using np.random.exponential for exponential arrival interval
        yield env.timeout(np.random.exponential(6.0)) 
        wp_id += 1
        env.process(factory.workpiece_flow(wp_id))

# ==========================================
# 4. Interactive Live Rendering Engine
# ==========================================
def run_visual_simulation(num_agvs=4, total_sim_time=240):
    env = simpy.Environment()
    factory = FactorySystem(env, num_agvs)
    env.process(source_generator(env, factory))
    
    # Initialize interactive plotting window
    plt.ion()
    fig, ax = plt.subplots(figsize=(12, 7))
    
    sim_step = 0.5 # Simulation minutes advanced per frame
    current_sim_time = 0.0
    
    while current_sim_time < total_sim_time:
        # Step the simulation engine forward
        env.run(until=current_sim_time + sim_step)
        current_sim_time = env.now
        
        # Refresh smooth spatial coordinates of AGVs
        for agv in factory.agv_fleet:
            agv.update_position(current_sim_time)
            
        # --------- Clear and Redraw Factory Layout ---------
        ax.clear()
        ax.set_xlim(0, 11)
        ax.set_ylim(0, 10)
        ax.axis('off')
        ax.set_facecolor('#fafafa')
        
        # 1. AS/RS Station
        ax.add_patch(plt.Rectangle((0.5, 4.0), 2.0, 2.0, color='#2b5c8f', alpha=0.7, edgecolor='black', lw=1.5))
        ax.text(1.5, 5.0, "AS/RS\n(Central Whse)", color='white', ha='center', va='center', fontweight='bold', fontsize=10)
        # 2. WIP Buffer Area
        ax.add_patch(plt.Rectangle((4.0, 0.5), 2.0, 1.2, color='#7f8c8d', alpha=0.6, edgecolor='black'))
        ax.text(5.0, 1.1, "WIP Buffer\n[Temp Racks]", color='white', ha='center', va='center', fontsize=9)
        # 3. CNC Station B (Bottleneck)
        ax.add_patch(plt.Rectangle((7.5, 6.5), 2.0, 2.0, color='#c0392b', alpha=0.7, edgecolor='black', lw=1.5))
        ax.text(8.5, 7.5, "CNC Station B\n(Bottleneck)", color='white', ha='center', va='center', fontweight='bold', fontsize=10)
        # 4. CNC Station C (Standard)
        ax.add_patch(plt.Rectangle((7.5, 3.5), 2.0, 2.0, color='#d35400', alpha=0.7, edgecolor='black'))
        ax.text(8.5, 4.5, "CNC Station C\n(Standard)", color='white', ha='center', va='center', fontsize=10)
        # 5. Quality Control Station (Sink)
        ax.add_patch(plt.Rectangle((4.0, 7.8), 2.0, 1.4, color='#27ae60', alpha=0.7, edgecolor='black'))
        ax.text(5.0, 8.5, "QC Inspection\n[Finished Sink]", color='white', ha='center', va='center', fontsize=10)

        # --------- Live Queue Length Text Indicators ---------
        q_b = len(factory.cnc_b.queue)
        q_c = len(factory.cnc_c.queue)
        
        # Color coding: text turns bold red if queue length >= 3 (Congested)
        color_b = 'red' if q_b >= 3 else 'black'
        weight_b = 'bold' if q_b >= 3 else 'normal'
        
        ax.text(8.5, 8.8, f"Queue: {q_b} pcs", color=color_b, fontweight=weight_b, ha='center', fontsize=11)
        ax.text(8.5, 5.8, f"Queue: {q_c} pcs", color='black', ha='center', fontsize=11)

        # --------- Render Mobile Entities: AGV Fleet ---------
        for agv in factory.agv_fleet:
            # Loaded AGV -> Cyan big block; Empty AGV -> Grey small block
            agv_color = '#1abc9c' if agv.has_load else '#bdc3c7'
            agv_size = 220 if agv.has_load else 120
            ax.scatter(agv.pos[0], agv.pos[1], s=agv_size, c=agv_color, marker='s', edgecolors='black', zorder=5)
            # Label identifier above the vehicle
            ax.text(agv.pos[0], agv.pos[1] + 0.35, f"AGV-{agv.id}", ha='center', fontsize=8, fontweight='bold')

        # --------- Live Performance Metrics Dashboard (KPIs) ---------
        avg_wait_b = np.mean(factory.cnc_b_waits) if factory.cnc_b_waits else 0.0
        avg_wait_c = np.mean(factory.cnc_c_waits) if factory.cnc_c_waits else 0.0
        agv_util = (factory.total_agv_busy_time) / (max(current_sim_time, 0.1) * num_agvs)
        agv_util = min(agv_util, 1.0) # Boundary capping
        
        # Header banner background
        ax.add_patch(plt.Rectangle((0.1, 9.2), 10.8, 0.7, color='#2c3e50'))
        dashboard_text = (
            f" [DASHBOARD] Time: {current_sim_time:5.1f} min  |  "
            f"Throughput: {factory.total_output:3d} pcs  |  "
            f"Avg Wait B: {avg_wait_b:4.2f} min  |  "
            f"Avg Wait C: {avg_wait_c:4.2f} min  |  "
            f"AGV Utilization: {agv_util:.1%}"
        )
        ax.text(5.5, 9.45, dashboard_text, color='#f1c40f', ha='center', va='center', fontsize=10, fontweight='bold', fontname='Courier New')

        # Draw frame and pause for live rendering
        plt.draw()
        plt.pause(FRAME_SPEED)
        
    plt.ioff()
    plt.show()

if __name__ == "__main__":
    # Run the visualization for 4 AGVs with a 240-minute simulation duration
    run_visual_simulation(num_agvs=1, total_sim_time=240)