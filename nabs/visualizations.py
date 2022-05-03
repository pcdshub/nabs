import matplotlib.pyplot as plt

from .plan_stubs import get_sample_targets


def show_shot_targets(sample_name, path):
    """
    Display a plot with targets.

    This class is used in conjunction witht the `XYGridStage` object from
    `pcdsdevices` as well as the `fixed_target_scan` from `nabs.plans`.
    It displays a scatter plot with the targets that have been scanned (& shot)
    with `fixed_target_scan`, and the targets that are still available.
    It uses the information saved in an yaml file for a specific sample
    to get the x and y positions as well as the last target that has been shot.
    This information is saved with the help of the `XYGridStage` object.

    Parameters
    ----------
    sample_name : str
        The name of the sample file to plot the graph for.
    path : str
        The path of the sample file.
    mn_format : bool
        Indicates if the graph should be represented in terms of M and N
        points rather than x and y positions.
    """
    plt.clf()
    xx, yy = get_sample_targets(sample_name, path)

    # find the index of the next target to be shot
    # if can't find it, assume all targets were shot
    x_index = next((index for (index, d) in enumerate(xx)
                   if d['status'] is False), len(xx))

    xx_shot = [item['pos'] for item in xx if item['status'] is True]
    yy_shot = [item['pos'] for item in yy if item['status'] is True]
    xx_available = [item['pos'] for item in xx if item['status'] is False]
    yy_available = [item['pos'] for item in yy if item['status'] is False]
    plt.plot(xx_available, yy_available, 'o', color='blue', markersize=1,
             label="available")
    plt.plot(xx_shot, yy_shot, 'o', color='orange', markersize=1, label="shot")
    plt.gca().invert_yaxis()
    plt.xlabel('X Target Positions')
    plt.ylabel('Y Target Positions')
    last_shot_index = x_index - 1
    if (last_shot_index) > 0:
        plt.plot(xx_shot[-1], yy_shot[-1],
                 '*', color='red', markersize=2, label='last shot index')
        last_shot_pos = xx_shot[last_shot_index], yy_shot[last_shot_index]

        plt.annotate(f" {last_shot_pos[0]}\n {last_shot_pos[1]}",
                     (xx_shot[last_shot_index], yy_shot[last_shot_index]),
                     size=8, color='red')

    plt.legend(bbox_to_anchor=(0.15, -0.05), loc='upper center', ncol=3)
    plt.show()
