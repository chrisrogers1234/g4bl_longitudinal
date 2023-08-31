import os
import matplotlib
import g4bl_longitudinal
import xboa.hit
import xboa.bunch

def build_final_cooling_lattice(lattice_filename):
    cavities = [
        {
            "name":"pillbox_1",
            "inner_length":500.0,
            "frequency":0.020,
            "max_gradient":10.0,
            "phase":0.0,
            "z_position":1000.0*i,
        } for i in range(1, 2)
    ]
    beam_def = {
        "filename":"beam.txt",
        "out_dir":os.path.split(lattice_filename)[0],
        "beams":[{
            "type":"longitudinal_grid",
            "t_min":0.0, # ns
            "t_max":50.0, # ns
            "n_t_steps":51,
            "e_min":100,
            "e_max":150,
            "n_e_steps":1,
        }],
    }
    mass = xboa.common.pdg_pid_to_mass[13]
    hit = xboa.hit.Hit.new_from_dict({"pid":-13, "energy":125+mass, "mass":mass}, "pz")
    reference = {
        "p_start":hit["pz"],
    }
    my_linac = g4bl_longitudinal.G4BLLinac(lattice_filename)
    my_linac.rf_cavities = cavities
    my_linac.beam = beam_def
    my_linac.reference = reference
    my_linac.do_stochastics = 0 # e.g. decays
    my_linac.build_linac()
    return my_linac

class Analysis():
    def __init__(self, linac, plot_dir):
        self.out_dir = linac.out_dir()
        self.plot_dir = plot_dir
        self.clean_dir = True
        self.out_filename = os.path.join(self.out_dir, linac.output_file)+".txt"

    def load_data(self):
        self.bunch_list = xboa.bunch.Bunch.new_list_from_read_builtin("icool_for009", self.out_filename)

    def do_plots(self):
        g4bl_longitudinal.clean_dir(self.plot_dir, self.clean_dir)
        self.plot_time_energy()

    def get_time_energy(self, bunch):
        t_list = bunch.list_get_hit_variable(["t"], ["ns"])[0]
        e_list = bunch.list_get_hit_variable(["kinetic_energy"], ["ns"])[0]
        t_list = [t-t_list[1] for t in t_list]
        return t_list, e_list

    def plot_time_energy(self):
        figure = matplotlib.pyplot.figure()
        axes = figure.add_subplot(1, 1, 1)

        bunch_start = self.bunch_list[0]
        t_list, e_list = self.get_time_energy(bunch_start)
        axes.scatter(t_list, e_list, label=f"z {bunch_start[0]['z']} mm")

        bunch_end = self.bunch_list[-1]
        t_list, e_list = self.get_time_energy(bunch_end)
        axes.scatter(t_list, e_list, label=f"z {bunch_end[0]['z']} mm")

        axes.set_xlabel("$\\Delta$t [ns]")
        axes.set_ylabel("Kinetic energy [MeV]")
        axes.legend()
        figure.savefig(os.path.join(self.plot_dir, "time_energy.png"))


def main():
    lattice_filename = "output/linac.g4bl"
    my_linac = build_final_cooling_lattice(lattice_filename)
    my_execution = g4bl_longitudinal.G4BLExecution(my_linac)
    my_execution.execute()
    my_analysis = Analysis(my_linac, "output/plots")
    my_analysis.load_data()
    my_analysis.do_plots()



if __name__ == "__main__":
    main()
    matplotlib.pyplot.show(block=False)
    input("Press <CR> to end")
